from django.db import models

class NewsAnalysis(models.Model):
    original_text = models.TextField()
    rewritten_text = models.TextField()
    bias_score = models.FloatField(default=50.0)  # ✅ Set a default value
