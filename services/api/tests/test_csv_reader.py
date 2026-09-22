"""Tests for the Unit 2 CSV reader and normalizer."""

from io import StringIO
import unittest

from app.incidents.csv_reader import CsvReadError, read_incidents_csv


HEADER = (
    "ticket_id,date,client_company,category,description,agent_id,status,"
    "customer_email,satisfaction_score"
)


class CsvReaderTests(unittest.TestCase):
    def test_normalizes_whitespace_and_integer_score(self) -> None:
        csv_text = (
            f"{HEADER}\n"
            " NXV-000001 , 2024-01-18 , FinServ Group , ACCESS , "
            "Login issue , AGT-08 , CLOSED , customer@example.com , 5 \n"
        )

        rows = read_incidents_csv(StringIO(csv_text))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ticket_id, "NXV-000001")
        self.assertEqual(rows[0].client_company, "FinServ Group")
        self.assertEqual(rows[0].category, "ACCESS")
        self.assertEqual(rows[0].satisfaction_score, 5)
        self.assertNotIn("customer@example.com", repr(rows[0]))

    def test_empty_score_is_normalized_to_none(self) -> None:
        csv_text = f"{HEADER}\nNXV-000001,2024-01-18,Acme,OPEN,Some issue,AGT-01,OPEN,,\n"

        rows = read_incidents_csv(StringIO(csv_text))

        self.assertIsNone(rows[0].satisfaction_score)

    def test_non_numeric_score_is_preserved_for_future_validation(self) -> None:
        csv_text = f"{HEADER}\nNXV-000001,2024-01-18,Acme,OPEN,Some issue,AGT-01,OPEN,customer@example.com,abc\n"

        rows = read_incidents_csv(StringIO(csv_text))

        self.assertEqual(rows[0].satisfaction_score, "abc")

    def test_empty_file_requires_header(self) -> None:
        with self.assertRaisesRegex(CsvReadError, "header"):
            read_incidents_csv(StringIO(""))

    def test_missing_required_column_is_file_error(self) -> None:
        with self.assertRaisesRegex(CsvReadError, "missing required columns"):
            read_incidents_csv(StringIO("ticket_id,category\nNXV-1,ACCESS\n"))

    def test_malformed_row_width_is_file_error(self) -> None:
        with self.assertRaisesRegex(CsvReadError, "fewer columns"):
            read_incidents_csv(StringIO(f"{HEADER}\nNXV-000001,2024-01-18\n"))

    def test_csv_dataset_has_expected_row_count(self) -> None:
        rows = read_incidents_csv("scripts/incidents-nexova.csv")

        self.assertEqual(len(rows), 100)


if __name__ == "__main__":
    unittest.main()
