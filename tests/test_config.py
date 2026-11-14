
from busbuddy.config import (
    BASE_DIR,
    DATA_DIR,
    KNOWLEDGE_BASE_DIR,
    DATABASE_PATH,
    LLM_AVAILABLE,
)


def test_project_directory_exists():
    assert BASE_DIR.exists()


def test_data_directory_exists():
    assert DATA_DIR.exists()


def test_knowledge_base_directory_exists():
    assert KNOWLEDGE_BASE_DIR.exists()


def test_database_path_is_inside_data_directory():
    assert DATABASE_PATH.parent == DATA_DIR


def test_llm_available_is_boolean():
    assert isinstance(LLM_AVAILABLE, bool)
