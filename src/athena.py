\
import time
import boto3
import pandas as pd


class AthenaClient:
    def __init__(self, region, database, output_s3, workgroup="primary",
                 profile_name=None):
        self.database = database
        self.output_s3 = output_s3
        self.workgroup = workgroup
        session = boto3.Session(profile_name=profile_name)
        self.client = session.client("athena", region_name=region)

    def start(self, sql):
        response = self.client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": self.database},
            ResultConfiguration={"OutputLocation": self.output_s3},
            WorkGroup=self.workgroup,
        )
        return response["QueryExecutionId"]

    def wait(self, query_execution_id, poll_seconds=0.6):
        while True:
            response = self.client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            query = response["QueryExecution"]
            state = query["Status"]["State"]

            if state == "SUCCEEDED":
                return query

            if state in {"FAILED", "CANCELLED"}:
                reason = query["Status"].get("StateChangeReason", state)
                raise RuntimeError(f"Athena query {state}: {reason}")

            time.sleep(poll_seconds)

    def results(self, query_execution_id):
        paginator = self.client.get_paginator("get_query_results")

        rows = []
        columns = None
        header_skipped = False

        for page in paginator.paginate(QueryExecutionId=query_execution_id):
            result_set = page["ResultSet"]

            if columns is None:
                columns = [
                    item["Name"]
                    for item in result_set["ResultSetMetadata"]["ColumnInfo"]
                ]

            for row in result_set["Rows"]:
                values = [
                    cell.get("VarCharValue")
                    for cell in row.get("Data", [])
                ]
                values += [None] * (len(columns) - len(values))

                if not header_skipped:
                    header_skipped = True
                    continue

                rows.append(values[:len(columns)])

        return pd.DataFrame(rows, columns=columns or [])

    def run(self, sql):
        query_id = self.start(sql)
        execution = self.wait(query_id)
        df = self.results(query_id)

        stats = execution.get("Statistics", {})
        metadata = {
            "query_execution_id": query_id,
            "engine_execution_ms": stats.get("EngineExecutionTimeInMillis"),
            "total_execution_ms": stats.get("TotalExecutionTimeInMillis"),
            "data_scanned_bytes": stats.get("DataScannedInBytes"),
        }

        return df, metadata
