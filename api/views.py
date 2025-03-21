import json
import requests
import openai
import re
from bs4 import BeautifulSoup
from newspaper import Article
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from .models import NewsAnalysis

# ✅ OpenAI API Key
openai.api_key = settings.OPENAI_API_KEY

# ✅ API Keys for Alternative Perspectives
NEWS_API_KEY = "357ea330ce7d4b1dbb9c9136cd2d5f62"
GNEWS_API_KEY = "16b9244ea8ad693aa9e9529a544ba766"

# ✅ Home Page
def home(request):
    return render(request, 'home.html')
def analyse(request):
    return render(request, 'index.html')

def about(request):
    return render(request, 'about.html')

# ✅ Extract News Content from URL
def extract_text_from_url(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text.strip() or "❌ Failed to extract content."
    except:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, "html.parser")
            paragraphs = soup.find_all("p")
            text = "\n".join([p.get_text() for p in paragraphs])
            return text.strip() if text else "❌ Could not extract article text."
        except:
            return "❌ Could not extract article text."

# ✅ GPT-4 Analysis Functions
def gpt4_analysis(prompt_system, prompt_user):
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": prompt_user}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ GPT Error: {str(e)}"

# ✅ Fake News Classification using GPT-4
def classify_fake_news(text):
    response = gpt4_analysis(
        "Analyze this news article's credibility. Consider: Source reliability, evidence provided, corroboration with known facts, and logical consistency. "
        "Respond with JSON: {label: 'Verified True', 'Likely True', 'Unverified', 'Likely False', 'Confirmed False', confidence: 0-100, explanation: 'bullet points'}",
        f"ARTICLE TEXT:\n{text}\n\nANALYSIS REQUESTED:"
    )
    try:
        return json.loads(response)
    except:
        return {"label": "Analysis Error", "confidence": 0, "explanation": "Failed to process credibility assessment"}

# ✅ Bias Score Calculation using GPT-4 (0-100)
def calculate_bias_score(text):
    response = gpt4_analysis(
        "Analyze the political bias in this article. Rate the bias from 0 (completely neutral) to 100 (extremely biased). "
        "Respond in JSON format: {score: number, explanation: 'brief reason'}",
        f"Text to analyze:\n{text}"
    )
    try:
        result = json.loads(response)
        score = min(max(int(result.get('score', 50)), 0), 100)  # Ensuring 0 ≤ score ≤ 100
        return score, result.get('explanation', 'No explanation available.')
    except:
        return 50, "Bias analysis failed"

# ✅ Rewrite Biased News using GPT-4
def rewrite_news_with_gpt(news_text):
    return gpt4_analysis(
        "You are an AI that rewrites biased news into neutral and factual versions.",
        f"Rewrite this news in a neutral way:\n\n{news_text}"
    )

# ✅ Summarize News using GPT-4
def summarize_news(news_text):
    return gpt4_analysis(
        "You are an AI that summarizes news articles concisely and accurately.",
        f"Summarize this news:\n\n{news_text}"
    )

# ✅ Fetch Alternative Perspectives from Multiple News Sources
def fetch_alternative_perspectives(query):
    perspectives = []

    # NewsAPI
    params = {"q": query, "apiKey": NEWS_API_KEY, "language": "en", "sortBy": "relevancy"}
    try:
        newsapi_response = requests.get("https://newsapi.org/v2/everything", params=params)
        if newsapi_response.status_code == 200:
            for article in newsapi_response.json().get("articles", [])[:3]:
                perspectives.append({
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                })
    except:
        pass  # Silently fail if API is unavailable

    # GNews API
    gnews_url = f"https://gnews.io/api/v4/search?q={query}&lang=en&token={GNEWS_API_KEY}"
    try:
        gnews_response = requests.get(gnews_url)
        if gnews_response.status_code == 200:
            for article in gnews_response.json().get("articles", [])[:3]:
                perspectives.append({
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                })
    except:
        pass  # Silently fail if API is unavailable

    return perspectives

# ✅ Fetch Fact Check Results from Google API
def fetch_fact_check_results(query):
    FACT_CHECK_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    params = {"query": query, "languageCode": "en"}
    try:
        response = requests.get(FACT_CHECK_API_URL, params=params)
        if response.status_code == 200:
            claims = response.json().get("claims", [])
            if claims:
                first_claim = claims[0].get("claimReview", [{}])[0]
                return {
                    "source": first_claim.get("publisher", {}).get("name", "Unknown"),
                    "verdict": first_claim.get("textualRating", "Unknown"),
                    "url": first_claim.get("url", "")
                }
    except:
        pass  # Fail silently if API request fails
    return None

@api_view(["POST"])
@csrf_exempt
def analyze_news(request):
    try:
        data = json.loads(request.body)
        news_text = data.get("news_text", "").strip()
        news_url = data.get("news_url", "").strip()

        if news_url:
            extracted_text = extract_text_from_url(news_url)
            if extracted_text.startswith("❌"):
                return JsonResponse({"error": "URL extraction failed"}, status=400)
            news_text = extracted_text

        if not news_text:
            return JsonResponse({"error": "No text provided"}, status=400)

        # Core Analysis
        credibility = classify_fake_news(news_text)
        bias_score, bias_explanation = calculate_bias_score(news_text)
        summary = summarize_news(news_text)
        rewritten = rewrite_news_with_gpt(news_text)
        
        # Additional Context
        keyword_query = " ".join(re.findall(r'\b\w+\b', news_text)[:8])
        perspectives = fetch_alternative_perspectives(keyword_query)
        fact_check = fetch_fact_check_results(keyword_query)

        # Save Results
        NewsAnalysis.objects.create(
            original_text=news_text,
            rewritten_text=rewritten,
            bias_score=bias_score
        )

        return JsonResponse({
            "credibility": credibility,
            "bias": {"score": bias_score, "explanation": bias_explanation},
            "summary": summary,
            "rewritten": rewritten,
            "perspectives": perspectives,
            "fact_check": fact_check,
            "status": "success"
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
