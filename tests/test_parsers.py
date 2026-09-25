"""
Unit tests for Erowid HTML Parsers and Adverse Event Extraction.
"""

import unittest
from erowid_safedb.parsers import ErowidExperienceParser, ErowidSubstanceParser


class TestParsers(unittest.TestCase):

    SAMPLE_HTML = """
    <!DOCTYPE HTML>
    <html>
    <head><title>2C-B - Erowid Exp - 'Massive Mistake'</title></head>
    <body>
    <div class="title">Massive Mistake</div>
    <div class="substance">2C-B & Cannabis</div>
    <div class="author">by <a href="#">tripper99</a></div>
    <table class="footdata">
        <tr><td class="footdata-expyear">Exp Year: 2019</td><td class="footdata-expid">ExpID: 55432</td></tr>
        <tr><td class="footdata-gender">Gender: Male</td><td>&nbsp;</td></tr>
        <tr><td class="footdata-ageofexp">Age at time of experience: 21</td></tr>
        <tr><td class="footdata-pubdate">Published: Aug 12, 2020</td></tr>
    </table>
    <table class="dosechart">
        <tr>
            <td class="dosechart-amount">25 mg</td>
            <td class="dosechart-method">Oral</td>
            <td class="dosechart-substance">2C-B</td>
            <td class="dosechart-form">Powder</td>
        </tr>
    </table>
    <table class="bodyweight">
        <tr><td class="bodyweight-title">BODY WEIGHT:</td><td class="bodyweight-amount">75 kg</td></tr>
    </table>
    <div class="report-text-surround">
        I took 25mg of 2C-B. At T+1:00 my heart started racing rapidly. I experienced severe tachycardia and felt like I was having a panic attack.
        My friend called 911 and the ambulance arrived. I was transported to the emergency room and admitted to the hospital for observation.
    </div>
    </body>
    </html>
    """

    def test_parse_experience(self):
        report = ErowidExperienceParser.parse_html(self.SAMPLE_HTML, fallback_id=55432)
        self.assertEqual(report.id, 55432)
        self.assertEqual(report.title, "Massive Mistake")
        self.assertEqual(report.author, "tripper99")
        self.assertEqual(report.substance_summary, "2C-B & Cannabis")
        self.assertEqual(report.exp_year, 2019)
        self.assertEqual(report.gender, "Male")
        self.assertEqual(report.age, "21")
        self.assertEqual(report.body_weight, "75 kg")
        self.assertEqual(len(report.doses), 1)
        self.assertEqual(report.doses[0].substance, "2C-B")
        self.assertEqual(report.doses[0].amount, "25")
        self.assertEqual(report.doses[0].unit, "mg")

    def test_adverse_signal_extraction(self):
        report = ErowidExperienceParser.parse_html(self.SAMPLE_HTML, fallback_id=55432)
        # Should detect tachycardia, panic_attack, hospitalization
        symptoms = [a.symptom for a in report.adverse_events]
        self.assertIn("tachycardia", symptoms)
        self.assertIn("panic_attack", symptoms)
        self.assertIn("hospitalization", symptoms)
        self.assertIn("Hospitalization", report.harm_flags)


if __name__ == "__main__":
    unittest.main()
