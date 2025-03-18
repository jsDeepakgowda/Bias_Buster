import torch
import json
import requests
import openai
import re
from bs4 import BeautifulSoup
from newspaper import Article
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from rest_framework.decorators import api_view
from django.views.decorators.csrf import csrf_exempt
from textblob import TextBlob
from .models import NewsAnalysis

# ✅ OpenAI API Key
openai.api_key = settings.OPENAI_API_KEY

# ✅ API Keys for Alternative Perspectives
NEWS_API_KEY = "357ea330ce7d4b1dbb9c9136cd2d5f62"
GNEWS_API_KEY = "16b9244ea8ad693aa9e9529a544ba766"

HF_API_TOKEN = settings.HUGGINGFACE_TOKEN
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"}

# ✅ Home Page
def home(request):
    return render(request, "index.html")

# ✅ Fake News Classification using BART
def classify_fake_news(text):
    payload = {"inputs": text, "parameters": {"candidate_labels": ["Real News", "Fake News"]}}
    response = requests.post(HF_API_URL, headers=HEADERS, json=payload)
    result = response.json()
    return {"label": result["labels"][0]} if "labels" in result else {"label": "Unknown"}

# ✅ Extract News Content from URL
def extract_text_from_url(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, "html.parser")
            paragraphs = soup.find_all("p")
            text = "\n".join([p.get_text() for p in paragraphs])
            return text if text else "❌ Failed to extract content."
        except:
            return "❌ Could not extract article text."

# ✅ Bias Score Calculation (0-100)
def calculate_bias_score(text):
    polarity = TextBlob(text).sentiment.polarity
    return round((polarity + 1) * 50, 2)

# ✅ Rewrite Biased News using GPT-4
def rewrite_news_with_gpt(news_text):
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an AI that rewrites biased news into neutral and factual versions."},
            {"role": "user", "content": f"Rewrite this news in a neutral way:\n\n{news_text}"}
        ]
    )
    return response.choices[0].message.content.strip()

# ✅ Summarize News using GPT-4
def summarize_news(news_text):
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an AI that summarizes news articles concisely and accurately."},
            {"role": "user", "content": f"Summarize this news:\n\n{news_text}"}
        ]
    )
    return response.choices[0].message.content.strip()

# ✅ Fetch Alternative Perspectives from Multiple News Sources
def fetch_alternative_perspectives(query):
    perspectives = []

    # ✅ Fetch from NewsAPI
    params = {"q": query, "apiKey": NEWS_API_KEY, "language": "en", "sortBy": "relevancy"}
    response = requests.get("https://newsapi.org/v2/everything", params=params)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        for article in articles[:3]:  # Limit to 3 per API
            perspectives.append({
                "source": article.get("source", {}).get("name", "Unknown"),
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "sentiment": classify_fake_news(article.get("content", article.get("description", ""))).get("label")
            })

    # ✅ Fetch from GNews API
    GNEWS_URL = f"https://gnews.io/api/v4/search?q={query}&lang=en&token={GNEWS_API_KEY}"
    response = requests.get(GNEWS_URL)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        for article in articles[:3]:
            perspectives.append({
                "source": article.get("source", {}).get("name", "Unknown"),
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "sentiment": classify_fake_news(article.get("content", article.get("description", ""))).get("label")
            })

    return perspectives
def fetch_fact_check_results(query):
    FACT_CHECK_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    params = {
        "query": query,
        "key": "YOUR_GOOGLE_FACT_CHECK_API_KEY",
        "languageCode": "en"
    }
    response = requests.get(FACT_CHECK_API_URL, params=params)
    
    if response.status_code == 200:
        fact_check_data = response.json().get("claims", [])
        if fact_check_data:
            return {
                "source": fact_check_data[0]["claimReview"][0]["publisher"]["name"],
                "verdict": fact_check_data[0]["claimReview"][0]["textualRating"],
                "url": fact_check_data[0]["claimReview"][0]["url"]
            }
    return None


# 
@api_view(["POST"])
@csrf_exempt
def analyze_news(request):
    try:
        data = json.loads(request.body)
        news_text = data.get("news_text", "").strip()
        news_url = data.get("news_url", "").strip()

        # ✅ Extract text from URL if provided
        if news_url:
            extracted_text = extract_text_from_url(news_url)
            if extracted_text.startswith("❌"):
                return JsonResponse({"status": "error", "message": "Failed to extract content from the URL."}, status=400)
            news_text = extracted_text

        if not news_text:
            return JsonResponse({"status": "error", "message": "News text or a valid URL is required."}, status=400)

        # ✅ Fake News Classification
        fake_news_result = classify_fake_news(news_text)

        # ✅ Summarization & Rewriting
        summary = summarize_news(news_text)
        rewritten_text = rewrite_news_with_gpt(news_text)

        # ✅ Bias Score Calculation
        bias_score = calculate_bias_score(news_text)

        # ✅ Fetch Alternative Perspectives
        keyword_query = " ".join(re.findall(r'\b\w+\b', news_text)[:8])
        perspectives = fetch_alternative_perspectives(keyword_query)

        # ✅ Fact-Checking using Google Fact Check API (if available)
        fact_check_result = fetch_fact_check_results(keyword_query)

        # ✅ Determine Final Credibility based on Alternative Sources & Fact-Checking
        real_count = sum(1 for p in perspectives if p["sentiment"] == "Real News")
        fake_count = sum(1 for p in perspectives if p["sentiment"] == "Fake News")

        if fact_check_result:
            final_credibility = fact_check_result["verdict"]
        elif real_count > fake_count:
            final_credibility = "Likely Real News"
        elif fake_count > real_count:
            final_credibility = "Likely Fake News"
        else:
            final_credibility = fake_news_result["label"]

        # ✅ Save to Database
        NewsAnalysis.objects.create(original_text=news_text, rewritten_text=rewritten_text, bias_score=bias_score)

        return JsonResponse({
            "status": "success",
            "bias_score": bias_score,
            #"news_credibility": final_credibility,
            "summary": summary,
            "rewritten_text": rewritten_text,
            "perspectives": perspectives if perspectives else "No alternative perspectives found.",
            "fact_check_result": fact_check_result if fact_check_result else "No fact-checking results available."
        })

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON input."}, status=400)
