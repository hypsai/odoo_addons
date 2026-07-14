from .test_base import TestBase


class TestFieldConfidence(TestBase):

    def test_01_fields_existence(self):
        """Verify age_confidence and overall confidence were generated."""
        model = self.env['confidence.test.age']
        self.assertIn('age_confidence', model._fields)
        self.assertIn('confidence', model._fields)

    def test_02_confidence_calculation(self):
        """Verify overall confidence picks the minimum value."""
        test_record = self.env['confidence.test.age'].create({
            'name': 'Test User',
            'age': 25,
            'age_confidence': 70
        })
        # The value is rolled back automatically after this test!
        self.assertEqual(test_record.confidence, 70)

        test_record.write({'age_confidence': 40})
        self.assertEqual(test_record.confidence, 40)