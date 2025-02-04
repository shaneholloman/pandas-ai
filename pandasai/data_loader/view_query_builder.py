import re
from typing import Dict

from pandasai.data_loader.loader import DatasetLoader
from pandasai.data_loader.query_builder import QueryBuilder
from pandasai.data_loader.semantic_layer_schema import SemanticLayerSchema
from pandasai.data_loader.sql_loader import SQLDatasetLoader


class ViewQueryBuilder(QueryBuilder):
    def __init__(
        self,
        schema: SemanticLayerSchema,
        schema_dependencies_dict: Dict[str, DatasetLoader],
    ):
        super().__init__(schema)
        self.schema_dependencies_dict = schema_dependencies_dict

    def build_query(self) -> str:
        columns = self._get_columns()
        query = f"SELECT {columns} "
        query += self._get_from_statement()
        query += self._add_order_by()
        query += self._add_limit()
        return query

    def _get_columns(self) -> str:
        if self.schema.columns:
            return ", ".join(
                [f"{col.name.replace('.', '_')}" for col in self.schema.columns]
            )
        else:
            return super()._get_columns()

    def _get_columns_for_table(self, query):
        match = re.search(r"SELECT\s+(.*?)\s+FROM", query, re.IGNORECASE)
        if not match:
            return None

        columns = match.group(1).split(",")
        return [col.strip() for col in columns]

    def _get_sub_query_from_loader(self, loader: SQLDatasetLoader) -> (str, str):
        query = loader.query_builder.build_query()
        return query, loader.schema.name

    def _get_from_statement(self):
        relations = self.schema.relations
        first_dataset = relations[0].from_.split(".")[0]
        first_loader = self.schema_dependencies_dict[first_dataset]

        if isinstance(first_loader, SQLDatasetLoader):
            first_query, first_name = self._get_sub_query_from_loader(first_loader)
        else:
            raise ValueError(
                "Views for local datasets or nested views are currently not supported."
            )

        query = f"FROM ( SELECT\n"

        if self.schema.columns:
            query += ", ".join(
                [
                    f"{col.name} AS {col.name.replace('.', '_')}"
                    for col in self.schema.columns
                ]
            )
        else:
            query += "* "

        query += f"\nFROM ( {first_query} ) AS {first_name}"
        for relation in relations:
            to_datasets = relation.to.split(".")[0]
            loader = self.schema_dependencies_dict[to_datasets]
            subquery, dataset_name = self._get_sub_query_from_loader(loader)
            query += f"\nJOIN ( {subquery} ) AS {dataset_name}\n"
            query += f"ON {relation.from_} = {relation.to}"
        query += f") AS {self.schema.name}\n"

        return query

    def get_head_query(self, n=5):
        columns = self._get_columns()
        query = f"SELECT {columns}"
        query += self._get_from_statement()
        return f"{query} LIMIT {n}"
