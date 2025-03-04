import time
import logging
from azure.data.tables import TableServiceClient
from azure.core.pipeline.policies import RetryPolicy, RetryMode
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError, AzureError, ServiceRequestError, HttpResponseError

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Global table clients
tables = {}

# Configure retry policy for resilience
retry_policy = RetryPolicy(
    retry_mode=RetryMode.Exponential,
    backoff_factor=2,
    backoff_max=60,
    total_retries=5
)

def init_tables():
    """Initialize Azure Table Storage connections and tables"""
    global tables
    
    # Skip if environment is test - handled elsewhere
    if settings.ENVIRONMENT == "test":
        logger.info("Running in TEST mode - initializing mock tables")
        
        # Create dummy table objects (won't actually connect to Azure)
        class MockTableClient:
            def __init__(self, table_name):
                self.name = table_name
                self._data = {}
            
            def create_entity(self, entity):
                self._data[entity.get("RowKey")] = entity
                return entity
                
            def get_entity(self, partition_key, row_key):
                if row_key not in self._data:
                    raise ResourceNotFoundError(f"Entity with row key {row_key} not found")
                return self._data.get(row_key, {})
                
            def list_entities(self, **kwargs):
                return list(self._data.values())
            
            def delete_entity(self, partition_key, row_key):
                if row_key in self._data:
                    del self._data[row_key]
                    
            def update_entity(self, entity, **kwargs):
                self._data[entity.get("RowKey")] = entity
        
        # Set up mock tables
        for table_name in ["Users", "Stars", "UserStars"]:
            tables[table_name] = MockTableClient(table_name)
            logger.info(f"Created mock table: {table_name}")
        
        return tables
    
    # Use managed identity if available, otherwise connection string
    connection_string = settings.AZURE.CONNECTION_STRING
    managed_identity_enabled = settings.AZURE.USE_MANAGED_IDENTITY
    
    logger.info(f"Initializing Azure Table Storage in {settings.ENVIRONMENT} environment")
    logger.info(f"Authentication method: {'Managed Identity' if managed_identity_enabled else 'Connection String'}")

    try:
        # Create the table service client
        if managed_identity_enabled:
            try:
                from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
                
                # Try DefaultAzureCredential first which works in more scenarios
                try:
                    credential = DefaultAzureCredential()
                    account_url = settings.AZURE.ACCOUNT_URL
                    table_service_client = TableServiceClient(
                        endpoint=account_url,
                        credential=credential,
                        retry_policy=retry_policy
                    )
                    logger.info("Using DefaultAzureCredential for Azure Table Storage authentication")
                except Exception as e:
                    logger.warning(f"DefaultAzureCredential failed: {str(e)}, trying ManagedIdentityCredential")
                    credential = ManagedIdentityCredential()
                    account_url = settings.AZURE.ACCOUNT_URL
                    table_service_client = TableServiceClient(
                        endpoint=account_url,
                        credential=credential,
                        retry_policy=retry_policy
                    )
                    logger.info("Using ManagedIdentityCredential for Azure Table Storage authentication")
            except ImportError as e:
                logger.error(f"azure.identity not installed but managed identity is enabled: {str(e)}")
                raise
        else:
            table_service_client = TableServiceClient.from_connection_string(
                connection_string,
                retry_policy=retry_policy
            )
            logger.info("Using connection string for Azure Table Storage authentication")

        # Initialize tables with retry logic
        for table_name in ["Users", "Stars", "UserStars"]:
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    table_service_client.create_table_if_not_exists(table_name)
                    tables[table_name] = table_service_client.get_table_client(table_name)
                    logger.info(f"Successfully initialized table: {table_name}")
                    break
                except (AzureError, ServiceRequestError, HttpResponseError) as e:
                    if attempt == max_attempts - 1:
                        logger.error(f"Failed to initialize table {table_name} after {max_attempts} attempts: {str(e)}")
                        raise
                    logger.warning(f"Failed to initialize table {table_name}, attempt {attempt+1}/{max_attempts}: {str(e)}")
                    time.sleep(2 ** attempt)  # Exponential backoff
    except Exception as e:
        logger.error(f"Failed to initialize Azure Table Storage: {str(e)}")
        if settings.ENVIRONMENT == "production":
            # In production, this is a critical failure
            raise
        else:
            # In development or staging, we can log and continue with empty tables
            logger.warning("Continuing with mock tables for development/staging")
            for table_name in ["Users", "Stars", "UserStars"]:
                tables[table_name] = None
                
    return tables
