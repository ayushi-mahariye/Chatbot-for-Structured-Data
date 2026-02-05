from typing import Dict, Optional, Any
import logging

# OpenAI client import (adjust to your codebase)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # gracefully degrade if not installed

# Langfuse (optional) - preserve behavior if available
try:
    from langfuse.openai import OpenAI as LangfuseOpenAI
    from langfuse import Langfuse
    from langfuse.decorators import observe, langfuse_context
    LANGFUSE_ENABLED = True
except Exception:
    LANGFUSE_ENABLED = False
    LangfuseOpenAI = None
    Langfuse = None
    # Define dummy decorators and context when Langfuse is not available
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    class LangfuseContextDummy:
        @staticmethod
        def update_current_trace(*args, **kwargs):
            pass
        
        @staticmethod
        def update_current_observation(*args, **kwargs):
            pass
    
    langfuse_context = LangfuseContextDummy()

# App config (adjust import path if required)
from app.core.config import settings

logger = logging.getLogger(__name__)


class SQLGenerator:
    """
    Generates PostgreSQL queries from natural language using an LLM or OpenAI client.
    
    Key features:
      - Centralized system prompt
      - Safe schema trimming
      - Post-processing to ensure SELECT-only and default LIMIT
      - Comprehensive Langfuse tracing with proper context management
      - Support for metadata, tags, user_id and session_id
      - Token usage tracking and cost monitoring
      - Error tracking with proper status levels
    """

    def __init__(self, ai_model: Optional[Any] = None):
        self.ai_model = ai_model
        self.langfuse_client = None
        
        # Initialize Langfuse client if enabled
        if LANGFUSE_ENABLED:
            try:
                self.langfuse_client = Langfuse(
                    secret_key=getattr(settings, "langfuse_secret_key", None),
                    public_key=getattr(settings, "langfuse_public_key", None),
                    host=getattr(settings, "langfuse_host", "https://cloud.langfuse.com"),
                    debug=getattr(settings, "langfuse_debug", False),
                    enabled=getattr(settings, "langfuse_enabled", True),
                    sample_rate=getattr(settings, "langfuse_sample_rate", 1.0),
                )
                # Optional: Test connection
                if getattr(settings, "langfuse_auth_check", False):
                    self.langfuse_client.auth_check()
                logger.info("Langfuse client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse client: {e}")
                self.langfuse_client = None
        
        # Initialize OpenAI client
        self.client = None
        if not ai_model and getattr(settings, "openai_api_key", None):
            try:
                # Use Langfuse-wrapped OpenAI client for automatic tracing
                if LANGFUSE_ENABLED and LangfuseOpenAI:
                    self.client = LangfuseOpenAI(api_key=settings.openai_api_key)
                    logger.info("Initialized Langfuse-wrapped OpenAI client")
                elif OpenAI:
                    self.client = OpenAI(api_key=settings.openai_api_key)
                    logger.info("Initialized standard OpenAI client")
            except Exception as e:
                logger.exception("Failed to initialize OpenAI client: %s", e)
                self.client = None

    # ---------------------------
    # Public generation entry with decorator for automatic tracing
    # ---------------------------
    async def generate_sql(
        self,
        question: str,
        schema_context: Dict,
        user_role: str,
        language: Optional[str] = None,
        sql_mode: str = "raw_sql",
        max_schema_chars: int = 9000,
        default_limit: int = 10,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[list] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        Generate SQL from a natural language question with comprehensive Langfuse tracing.
        
        Args:
            question: Natural language question
            schema_context: Database schema information
            user_role: User's role for access control
            language: Response language (optional)
            sql_mode: SQL generation mode (default: "raw_sql")
            max_schema_chars: Maximum schema context characters
            default_limit: Default LIMIT for queries
            user_id: User identifier for Langfuse tracking
            session_id: Session identifier for Langfuse tracking
            tags: List of tags for categorization
            metadata: Additional metadata to track
            
        Returns:
            Dict with sql_query and explanation, or error message
        """
        if self.ai_model:
            return await self._generate_with_ai_model(
                question=question,
                schema_context=schema_context,
                user_role=user_role,
                language=language,
                sql_mode=sql_mode,
                max_schema_chars=max_schema_chars,
                default_limit=default_limit,
                user_id=user_id,
                session_id=session_id,
                tags=tags,
                metadata=metadata,
            )

        if not self.client:
            return {"error": "No AI model or OpenAI API key configured"}

        # Use context manager for proper trace management
        return await self._generate_with_openai_trace(
            question=question,
            schema_context=schema_context,
            user_role=user_role,
            language=language,
            sql_mode=sql_mode,
            max_schema_chars=max_schema_chars,
            default_limit=default_limit,
            user_id=user_id,
            session_id=session_id,
            tags=tags,
            metadata=metadata,
        )

    # ---------------------------
    # OpenAI generation with proper Langfuse context management
    # ---------------------------
    async def _generate_with_openai_trace(
        self,
        question: str,
        schema_context: Dict,
        user_role: str,
        language: Optional[str],
        sql_mode: str,
        max_schema_chars: int,
        default_limit: int,
        user_id: Optional[str],
        session_id: Optional[str],
        tags: Optional[list],
        metadata: Optional[Dict],
    ) -> Dict:
        """Generate SQL with OpenAI client and comprehensive Langfuse tracing."""
        
        # Build prompts
        raw_schema_prompt = self._build_schema_prompt(schema_context)
        schema_prompt = self._trim_schema_prompt(raw_schema_prompt, max_chars=max_schema_chars)
        system_prompt = self._build_system_prompt(user_role, schema_prompt, language)
        
        # Prepare metadata for Langfuse with standardized structure
        trace_metadata = {
            # Request context
            "user_role": user_role,
            "question": question,
            "sql_mode": sql_mode,
            "language": language or "en",
            
            # Schema info
            "schema_size": len(schema_prompt),
            
            # Model info
            "model": "gpt-4.1-2025-04-14",
            "model_name": "gpt-4.1-2025-04-14",
            "model_type": "openai",
            "model_provider": "openai",
            
            # Version info
            "version": getattr(settings, "app_version", "1.0.0"),
            "environment": getattr(settings, "environment", "production"),
            
            # Additional metadata
            **(metadata or {})
        }
        
        # Prepare tags with consistent format
        trace_tags = [
            "sql_generation",           # Type of operation
            "provider:openai",          # Provider with prefix
            "model:gpt-4.1-2025-04-14",     # Model with prefix
            f"role:{user_role}",        # Role with prefix
        ]
        
        # Add optional tags with proper prefixes
        if tags:
            trace_tags.extend(tags)
        if language:
            trace_tags.append(f"lang:{language}")
        
        # Use context manager for proper trace hierarchy (recommended approach)
        if LANGFUSE_ENABLED and self.langfuse_client:
            try:
                # Create a standardized trace name with hierarchical format
                with self.langfuse_client.start_as_current_span(
                    name="sql_generation.openai"
                ) as span:
                    # Set trace-level attributes
                    span.update_trace(
                        user_id=user_id or user_role,
                        session_id=session_id,
                        tags=trace_tags,
                        metadata=trace_metadata,
                        version=getattr(settings, "app_version", "1.0.0"),
                        release=getattr(settings, "app_release", "production"),
                    )
                    
                    return await self._execute_openai_call(
                        system_prompt=system_prompt,
                        question=question,
                        user_role=user_role,
                        default_limit=default_limit,
                        trace_metadata=trace_metadata,
                    )
            except Exception as e:
                logger.exception(f"Langfuse tracing failed: {e}, continuing without trace")
                # Fall back to direct call without tracing
                return await self._execute_openai_call(
                    system_prompt=system_prompt,
                    question=question,
                    user_role=user_role,
                    default_limit=default_limit,
                    trace_metadata=trace_metadata,
                )
        else:
            # No Langfuse - direct call
            return await self._execute_openai_call(
                system_prompt=system_prompt,
                question=question,
                user_role=user_role,
                default_limit=default_limit,
                trace_metadata=trace_metadata,
            )

    async def _execute_openai_call(
        self,
        system_prompt: str,
        question: str,
        user_role: str,
        default_limit: int,
        trace_metadata: Dict,
    ) -> Dict:
        """Execute OpenAI API call with proper error handling and tracing."""
        
        try:
            # The Langfuse-wrapped client automatically creates a generation span
            # with proper token usage and cost tracking
            response = self.client.chat.completions.create(
                model="gpt-4.1-2025-04-14",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                max_tokens=500,
                temperature=0.1,
                # Pass metadata for this specific generation
                # (only works with Langfuse-wrapped client)
                **({
                    "name": "sql_generation.openai.completion",  # Hierarchical naming
                    "metadata": {
                        "generation_type": "sql",
                        "user_role": user_role,
                        "model": "gpt-4.1-2025-04-14",
                        "temperature": 0.1,
                        "max_tokens": 500
                    }
                } if LANGFUSE_ENABLED else {})
            )
            
            # Extract SQL from response
            sql_raw = self._extract_text_from_response(response)
            sql_query = self._postprocess_sql(sql_raw, default_limit=default_limit)
            
            result = {
                "sql_query": sql_query,
                "explanation": f"Generated SQL for role: {user_role}",
                "model": "gpt-4.1-2025-04-14",
                "tokens_used": getattr(response, "usage", None),
            }
            
            # Log successful generation with standardized metrics
            if LANGFUSE_ENABLED and self.langfuse_client:
                try:
                    # Update observation with standardized success metadata
                    langfuse_context.update_current_observation(
                        # Result data
                        output=result,
                        
                        # Enhanced metadata with performance indicators
                        metadata={
                            # Base metadata
                            **trace_metadata,
                            
                            # Status information
                            "status": "success",
                            "completion_status": "complete",
                            
                            # SQL metrics
                            "sql_length": len(sql_query),
                            "has_limit": "limit" in sql_query.lower(),
                            "query_complexity": len(sql_query.split("\n")),
                            "has_joins": "join" in sql_query.lower(),
                            
                            # Token usage if available
                            "tokens_used": getattr(response, "usage", {}).get("total_tokens") if hasattr(response, "usage") else None,
                        },
                        level="DEFAULT",
                    )
                except Exception as e:
                    logger.debug(f"Failed to update observation metadata: {e}")
            
            return result
            
        except Exception as e:
            error_msg = f"OpenAI API call failed: {str(e)}"
            logger.exception(error_msg)
            
            # Log error to Langfuse with proper level and standardized format
            if LANGFUSE_ENABLED and self.langfuse_client:
                try:
                    langfuse_context.update_current_observation(
                        # Error level and message
                        level="ERROR",
                        status_message=error_msg,
                        
                        # Enhanced error metadata
                        metadata={
                            # Base metadata
                            **trace_metadata,
                            
                            # Error details
                            "status": "error",
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "error_location": "openai_api_call",
                            "recoverable": False,
                            "retry_attempted": False,
                        },
                    )
                except Exception as e:
                    logger.debug(f"Failed to log error to Langfuse: {e}")
            
            return {"error": error_msg}

    # ---------------------------
    # AI model path with @observe decorator for automatic tracing
    # ---------------------------
    @observe(name="sql_generation.custom_model", as_type="generation")
    async def _generate_with_ai_model(
        self,
        question: str,
        schema_context: Dict,
        user_role: str,
        language: Optional[str],
        sql_mode: str,
        max_schema_chars: int,
        default_limit: int,
        user_id: Optional[str],
        session_id: Optional[str],
        tags: Optional[list],
        metadata: Optional[Dict],
    ) -> Dict:
        """
        Use a provided ai_model with @observe decorator for automatic tracing.
        
        The @observe decorator automatically:
        - Creates a trace/span hierarchy
        - Tracks inputs and outputs
        - Captures execution time
        - Logs errors with proper levels
        """
        
        # Build prompts
        raw_schema_prompt = self._build_schema_prompt(schema_context)
        schema_prompt = self._trim_schema_prompt(raw_schema_prompt, max_chars=max_schema_chars)
        system_prompt = self._build_system_prompt(user_role, schema_prompt, language)
        full_prompt = f"{system_prompt}\n\n{question}"
        
        # Prepare metadata with standardized structure
        model_type = self._get_model_type()
        model_name = getattr(self.ai_model, "name", "custom_model")
        
        model_metadata = {
            # Request context
            "user_role": user_role,
            "question": question,
            "sql_mode": sql_mode,
            "language": language or "en",
            
            # Schema info
            "schema_size": len(schema_prompt),
            
            # Model info
            "model": model_name,
            "model_name": model_name,
            "model_type": model_type,
            "model_provider": model_type,
            
            # Version info
            "version": getattr(settings, "app_version", "1.0.0"),
            "environment": getattr(settings, "environment", "production"),
            
            # Additional metadata
            **(metadata or {})
        }
        
        # Update current observation with metadata and trace attributes
        if LANGFUSE_ENABLED:
            try:
                # Prepare standardized tags with consistent format
                model_tags = [
                    "sql_generation",                # Type of operation
                    f"provider:{model_type}",        # Provider with prefix
                    f"model:{model_name}",           # Model with prefix
                    f"role:{user_role}",             # Role with prefix
                ]
                
                # Add optional tags
                if tags:
                    model_tags.extend(tags)
                if language:
                    model_tags.append(f"lang:{language}")
                    
                # Update trace with standardized attributes
                langfuse_context.update_current_trace(
                    # Identity attributes
                    user_id=user_id or user_role,
                    session_id=session_id,
                    
                    # Classification attributes
                    tags=model_tags,
                    metadata=model_metadata,
                    
                    # Version control attributes
                    version=getattr(settings, "app_version", "1.0.0"),
                    release=getattr(settings, "app_release", "production"),
                )
                
                # Update observation with standardized naming and input
                langfuse_context.update_current_observation(
                    # Hierarchical name format
                    name=f"sql_generation.{model_type}.completion",
                    
                    # Enhanced metadata
                    metadata=model_metadata,
                    
                    # Structured input
                    input={
                        "prompt": full_prompt,
                        "question": question,
                        "system_prompt_length": len(system_prompt),
                        "total_prompt_length": len(full_prompt)
                    },
                )
            except Exception as e:
                logger.debug(f"Failed to update Langfuse context: {e}")
        
        # Generate response
        try:
            # Try synchronous call first
            response = self.ai_model.generate_response(full_prompt)
        except TypeError:
            # Try async if sync fails
            try:
                response = await self.ai_model.generate_response(full_prompt)
            except Exception as e:
                error_msg = f"ai_model generation failed: {str(e)}"
                logger.exception(error_msg)
                
                # Update observation with standardized error reporting
                if LANGFUSE_ENABLED:
                    try:
                        langfuse_context.update_current_observation(
                            # Error level and message
                            level="ERROR",
                            status_message=error_msg,
                            
                            # Enhanced error metadata
                            metadata={
                                # Base metadata
                                **model_metadata,
                                
                                # Error details
                                "status": "error",
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "error_location": "ai_model_async_call",
                                "recoverable": False,
                            },
                        )
                    except Exception as e:
                        logger.debug(f"Failed to log error to Langfuse: {e}")
                
                return {"error": error_msg}
        except Exception as e:
            error_msg = f"ai_model generation failed: {str(e)}"
            logger.exception(error_msg)
            
            if LANGFUSE_ENABLED:
                try:
                    langfuse_context.update_current_observation(
                        # Error level and message
                        level="ERROR",
                        status_message=error_msg,
                        
                        # Enhanced error metadata
                        metadata={
                            # Base metadata
                            **model_metadata,
                            
                            # Error details
                            "status": "error",
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "error_location": "ai_model_sync_call",
                            "recoverable": False,
                        },
                    )
                except Exception as e:
                    logger.debug(f"Failed to log error to Langfuse: {e}")
            
            return {"error": error_msg}
        
        # Post-process SQL
        sql_query = self._postprocess_sql(response, default_limit=default_limit)
        
        result = {
            "sql_query": sql_query,
            "explanation": f"Generated SQL using {getattr(self.ai_model, 'name', 'ai_model')} for role: {user_role}",
            "model": getattr(self.ai_model, "name", "custom_model"),
        }
        
        # Update observation with standardized success metadata
        if LANGFUSE_ENABLED:
            try:
                langfuse_context.update_current_observation(
                    # Result data
                    output=result,
                    
                    # Enhanced metadata with performance indicators
                    metadata={
                        # Base metadata
                        **model_metadata,
                        
                        # Status information
                        "status": "success",
                        "completion_status": "complete",
                        
                        # SQL metrics
                        "sql_length": len(sql_query),
                        "has_limit": "limit" in sql_query.lower(),
                        "query_complexity": len(sql_query.split("\n")),
                        "has_joins": "join" in sql_query.lower(),
                        
                        # Model-specific
                        "model_provider": model_type,
                    },
                    level="DEFAULT",
                )
            except Exception as e:
                logger.debug(f"Failed to update observation with result: {e}")
        
        return result

    # ---------------------------
    # Helper methods (unchanged logic, added type hints)
    # ---------------------------
    def _build_schema_prompt(self, schema_context: Dict) -> str:
        """Build schema context text from schema_context dict."""
        prompt_parts = []
        for schema_name, schema_tables in schema_context.items():
            for table_name, table_info in schema_tables.items():
                cols = table_info.get("columns", [])
                display_cols = cols[:40]
                columns = ", ".join(display_cols)
                
                hints = []
                lower_table = table_name.lower()
                if lower_table in ("manufacturers", "manufacturers_clean"):
                    if "groupattributes_manufacturer_name_0" in cols:
                        hints.append("Prefer groupattributes_manufacturer_name_0 as manufacturer display name.")
                if lower_table in ("retailers", "retailers_clean"):
                    if "groupattributes_retailer_name_0" in cols:
                        hints.append("Prefer groupattributes_retailer_name_0 as retailer display name.")
                if lower_table in ("suppliers", "suppliers_clean"):
                    if "groupattributes_supplier_name_0" in cols:
                        hints.append("Prefer groupattributes_supplier_name_0 as supplier display name.")
                
                fk_hints = [c for c in cols if c.lower().endswith(("_id", "_1_id", "_2_id", "_3_id"))]
                hint_text = ""
                if hints or fk_hints:
                    hint_text = " Hints: " + "; ".join(hints + (["FKs: " + ", ".join(fk_hints)] if fk_hints else []))
                
                prompt_parts.append(f"Table: {table_name}\nColumns: {columns}{hint_text}\n")
        
        return "\n".join(prompt_parts)

    def _trim_schema_prompt(self, schema_prompt: str, max_chars: int = 9000) -> str:
        """Trim schema prompt to fit context window."""
        if not schema_prompt or len(schema_prompt) <= max_chars:
            return schema_prompt
        
        head = schema_prompt[: int(max_chars * 0.6)]
        tail = schema_prompt[-int(max_chars * 0.35) :]
        return head + "\n\n... [schema truncated to fit context] ...\n\n" + tail

    def _build_system_prompt(
        self, user_role: str, schema_prompt: str, language: Optional[str] = None
    ) -> str:
        """Centralized system prompt."""
        language_instruction = (
            f"\nRespond in {language} language. The SQL query should follow PostgreSQL syntax regardless of language."
            if language else ""
        )
        
        return (
            "You are a SQL expert. Generate PostgreSQL queries based on natural language questions.\n\n"
            f"User Role: {user_role}\n"
            f"Available Schema:\n{schema_prompt}\n\n"
            "Naming rules (must always follow):\n"
            "- Use groupattributes_manufacturer_name_0 as manufacturer display name.\n"
            "- Use groupattributes_retailer_name_0 as retailer display name.\n"
            "- Use groupattributes_supplier_name_0 as supplier display name.\n"
            "- Do NOT use `groupname` for these entities.\n\n"
            "Rules:\n"
            "1. Only use tables and columns available to this role\n"
            "2. Always generate SELECT queries only (no INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE)\n"
            "3. Always use proper PostgreSQL syntax\n"
            "4. Include LIMIT clauses for large result sets (default LIMIT 10 if not specified)\n"
            "5. Return only the SQL query, no explanations" + language_instruction + "\n"
            "6. Always alias complex or long column names with short, readable names\n"
            "7. Always join tables using their *_id relationships when appropriate\n"
            "8. Ensure the query is syntactically correct and executable without modification\n"
            "9. Do not wrap the output in markdown fences (```sql ... ```)\n\n"
            "Generate a SQL query for the following question:"
        )

    def _postprocess_sql(self, raw_sql: str, default_limit: int = 10) -> str:
        """Post-process and validate SQL."""
        if not raw_sql:
            return ""
        
        sql = raw_sql.strip()
        
        # Remove markdown fences
        if sql.startswith("```"):
            parts = sql.splitlines()
            if len(parts) > 1:
                parts = parts[1:]
                if parts and parts[-1].strip().endswith("```"):
                    parts = parts[:-1]
                sql = "\n".join(parts).strip()
        
        sql = sql.replace("```sql", "").replace("```SQL", "").strip()
        sql = " ".join(sql.split())
        
        lower = sql.lower()
        if not lower:
            return ""
        
        # Security check: only SELECT queries
        if not (lower.startswith("select") or lower.startswith("with")):
            return "SELECT 'ERROR: only SELECT queries allowed' AS error_message LIMIT 1;"
        
        # Add default LIMIT if missing
        if " limit " not in lower:
            if sql.endswith(";"):
                sql = sql[:-1].rstrip() + f" LIMIT {default_limit};"
            else:
                sql = f"{sql} LIMIT {default_limit}"
        
        return sql

    def _extract_text_from_response(self, response: Any) -> str:
        """Extract text from various response formats."""
        try:
            choices = getattr(response, "choices", None)
            if choices:
                first = choices[0]
                msg = getattr(first, "message", None)
                if msg is not None:
                    content = getattr(msg, "content", None)
                    if content:
                        return content
                text = getattr(first, "text", None)
                if text:
                    return text
            
            if isinstance(response, dict):
                try:
                    return response["choices"][0]["message"]["content"]
                except Exception:
                    try:
                        return response["choices"][0]["text"]
                    except Exception:
                        pass
        except Exception:
            logger.debug("Response parsing attempt failed, using fallback", exc_info=True)
        
        return str(response)

    def _get_model_type(self) -> str:
        """Determine model type from ai_model class name with standardized naming."""
        if not self.ai_model:
            return "default"
        
        # Standardized model type mapping
        model_class_name = self.ai_model.__class__.__name__
        model_mapping = {
            "Gemini": "gemini",
            "OpenAI": "openai",
            "Claude": "anthropic",  # Use provider name instead of model name
            "Nebius": "nebius",
            "Llama": "meta",       # Use provider name instead of model name
            "Deepseek": "deepseek",
            "Mistral": "mistral",
            "Cohere": "cohere",
        }
        
        # Check for model type matches
        for key, value in model_mapping.items():
            if key in model_class_name:
                return value
        
        # Default to custom if no match
        return "custom"

    def flush(self) -> None:
        """
        Flush pending Langfuse events.
        
        Important: Call this method before your application exits to ensure
        all traces are sent to Langfuse. This is especially important for
        short-lived applications or batch jobs.
        """
        if LANGFUSE_ENABLED and self.langfuse_client:
            try:
                self.langfuse_client.flush()
                logger.info("Langfuse events flushed successfully")
            except Exception as e:
                logger.warning(f"Failed to flush Langfuse events: {e}")

    def __del__(self):
        """Ensure Langfuse is flushed when the object is destroyed."""
        self.flush()