import os
import uuid
from typing import Union, Dict, Any
from loguru import logger
import chainlit.data as cl_data
from chainlit.data.storage_clients.base import BaseStorageClient
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
import psycopg2
from psycopg2 import sql

from app.utils import utils

db_name = os.getenv("POSTGRES_DB", "audio_notes")
db_user = os.getenv("POSTGRES_USER", "username")
db_password = os.getenv("POSTGRES_PASSWORD", "password")
db_host = os.getenv("POSTGRES_HOST", "localhost")
db_port = os.getenv("POSTGRES_PORT", "5432")


class StorageClient(BaseStorageClient):
    def __init__(self, bucket: str = ""):
        try:
            self.bucket = bucket
            logger.info("StorageClient initialized")
        except Exception as e:
            logger.warning(f"StorageClient initialization error: {e}")

    async def upload_file(self, object_key: str, data: Union[bytes, str], mime: str = 'application/octet-stream',
                          overwrite: bool = True) -> Dict[str, Any]:
        try:
            filename = str(uuid.uuid4())
            extname = os.path.splitext(object_key)[1].lower()
            object_key = filename + extname
            file_path = os.path.join(utils.upload_dir(), object_key)
            with open(file_path, 'wb') as f:
                f.write(data)
            return {"object_key": object_key, "url": f"/uploads/{object_key}"}
        except Exception as e:
            logger.warning(f"StorageClient, upload_file error: {e}")
            return {}

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from storage
        
        Args:
            file_path: Path to the file to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            full_path = os.path.join(utils.upload_dir(), file_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
            return False
        except Exception as e:
            logger.warning(f"StorageClient, delete_file error: {e}")
            return False

    def get_read_url(self, file_path: str) -> str:
        """Get a URL for reading the file
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: URL that can be used to read the file
        """
        try:
            # Since we're using local storage, return a relative URL path
            return f"/uploads/{file_path}"
        except Exception as e:
            logger.warning(f"StorageClient, get_read_url error: {e}")
            return ""


def get_connection_url(driver: str = "asyncpg"):
    return f"postgresql+{driver}://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


# 如果数据库不存在，会自动创建
def __init_db():
    conn = psycopg2.connect(dbname='postgres', user=db_user, password=db_password, host=db_host, port=db_port)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    if not exists:
        conn = psycopg2.connect(dbname='postgres', user=db_user, password=db_password, host=db_host, port=db_port)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        cur.close()
        conn.close()


def __init_tables():
    sql = '''
CREATE TABLE IF NOT EXISTS users (
    "id" UUID PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" JSONB NOT NULL,
    "createdAt" TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    "id" UUID PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" UUID,
    "userIdentifier" TEXT,
    "tags" TEXT[],
    "metadata" JSONB,
    FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS steps (
    "id" UUID PRIMARY KEY,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "threadId" UUID NOT NULL,
    "parentId" UUID,
    "disableFeedback" BOOLEAN NOT NULL DEFAULT false,
    "streaming" BOOLEAN NOT NULL DEFAULT false,
    "waitForAnswer" BOOLEAN DEFAULT false,
    "isError" BOOLEAN DEFAULT false,
    "metadata" JSONB DEFAULT '{}'::jsonb,
    "tags" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" JSONB DEFAULT '{}'::jsonb,
    "showInput" TEXT,
    "language" TEXT,
    "indent" INT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS elements (
    "id" UUID PRIMARY KEY,
    "threadId" UUID,
    "type" TEXT,
    "url" TEXT,
    "chainlitKey" TEXT,
    "name" TEXT NOT NULL,
    "display" TEXT,
    "objectKey" TEXT,
    "size" TEXT,
    "page" INT,
    "language" TEXT,
    "forId" UUID,
    "mime" TEXT
);

CREATE TABLE IF NOT EXISTS feedbacks (
    "id" UUID PRIMARY KEY,
    "forId" UUID NOT NULL,
    "value" INT NOT NULL,
    "comment" TEXT
);
    '''
    conn = psycopg2.connect(dbname=db_name, user=db_user, password=db_password, host=db_host, port=db_port)
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()


def init():
    __init_db()
    __init_tables()
    cl_data._data_layer = SQLAlchemyDataLayer(conninfo=get_connection_url(),
                                              storage_provider=StorageClient(),
                                              show_logger=False)
