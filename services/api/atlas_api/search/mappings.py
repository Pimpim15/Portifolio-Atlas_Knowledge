"""Definição da indexação no OpenSearch."""

DOC_INDEX = "docs_v1"

DOC_MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "pt_en_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding", "stop", "porter_stem"],
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "org_id": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "pt_en_analyzer"},
            "body": {"type": "text", "analyzer": "pt_en_analyzer"},
            "tags": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        }
    },
}
