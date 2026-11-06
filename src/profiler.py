\
from datetime import date, datetime
import json


def _safe_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


class GenBIProfiler:
    """
    Produces technical metadata + small samples.
    It deliberately does NOT define business semantics.
    """

    def __init__(self, athena_client, database, view_name):
        self.athena = athena_client
        self.database = database
        self.view_name = view_name

    def get_schema(self):
        sql = f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = '{self.database}'
          AND table_name = '{self.view_name}'
        ORDER BY ordinal_position
        """
        df, _ = self.athena.run(sql)
        return [
            {
                "name": row["column_name"],
                "type": row["data_type"],
            }
            for _, row in df.iterrows()
        ]

    def get_sample_rows(self, limit=8):
        sql = f'SELECT * FROM "{self.view_name}" LIMIT {int(limit)}'
        df, _ = self.athena.run(sql)
        return [
            {k: _safe_value(v) for k, v in record.items()}
            for record in df.to_dict(orient="records")
        ]

    def build_profile(self, business_context, sample_limit=8):
        schema = self.get_schema()
        samples = self.get_sample_rows(sample_limit)

        profile = {
            "dataset_name": business_context["dataset_name"],
            "business_domain": business_context.get("business_domain"),
            "database": self.database,
            "allowed_view": self.view_name,
            "grain_hint": business_context["grain"],
            "known_business_notes": business_context.get(
                "known_business_notes", []
            ),
            "columns": schema,
            "sample_rows": samples,
        }

        return profile


def save_profile(profile, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False, default=str)
