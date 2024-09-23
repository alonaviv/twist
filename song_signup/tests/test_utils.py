from django.test import TestCase
from twist.utils import format_commas

class TestFormatCommas(TestCase):
    def test_4_singers(self):
        singers = ["Alon Aviv", "Shani Wahrman", "Inbal Feldman", "Joey Geralnik"]
        expected_res = "Alon Aviv, Shani Wahrman, Inbal Feldman and Joey Geralnik"

        self.assertEqual(format_commas(singers), expected_res)

    def test_3_singers(self):
        singers = ["Alon Aviv", "Shani Wahrman", "Inbal Feldman"]
        expected_res = "Alon Aviv, Shani Wahrman and Inbal Feldman"

        self.assertEqual(format_commas(singers), expected_res)

    def test_2_singers(self):
        singers = ["Alon Aviv", "Shani Wahrman"]
        expected_res = "Alon Aviv and Shani Wahrman"

        self.assertEqual(format_commas(singers), expected_res)

    def test_1_singer(self):
        singers = ["Alon Aviv"]
        expected_res = "Alon Aviv"

        self.assertEqual(format_commas(singers), expected_res)

    def test_empty(self):
        singers = []
        expected_res = ""

        self.assertEqual(format_commas(singers), expected_res)
