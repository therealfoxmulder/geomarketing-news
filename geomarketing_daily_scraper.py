#!/usr/bin/env python3
"""
Geomarketing Daily News Aggregator - FIXED VERSION
Lädt täglich um 8 Uhr Geomarketing-relevante News von definierten Quellen
"""

import json
import os
from datetime import datetime
from typing import List, Dict
import requests
import time

SOURCES = {
    'DESTATIS': ['Einzelhandel', 'Demografie', 'Standort', 'Regionalentwicklung'],
    'BBSR': ['Infrastruktur', 'Nahversorgung', 'Leerstand', 'Stadtentwicklung'],
    'HDE': ['Filiale', 'Einzelhandelstrends', 'Versorgung', 'Filialnetz'],
    'IW Köln': ['Konjunktur', 'Regional', 'Wirtschaft', 'Kita'],
    'LinkedIn Geomarketing': ['Standortanalyse', 'Geomarketing', 'Location Intelligence'],
    'NIQ Reports': ['Kaufkraft', 'Zentralität', 'Crowd Monitor']
}

GEOMARKETING_KEYWORDS = [
    'standortanalyse', 'geomarketing', 'kaufkraft', 'zentralität', 'filialdichte',
    'demografie', 'nahversorgung', 'infrastruktur', 'einzelhandel', 'ladeinfrastruktur',
    'leerstand', 'besucherfrequenz', 'filialschließung', 'expansion', 'erreichbarkeit'
]

class GeomarketingNewsScraper:
    def __init__(self, anthropic_api_key: str = None):
        self.api_key = anthropic_api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Set it via environment variable or pass it directly.")
        self.results = []
        self.base_url = 'https://api.anthropic.com/v1/messages'
        
    def search_source(self, source_name: str, keywords: List[str]) -> List[Dict]:
        """Suche eine Quelle mit Keywords via Claude + Web Search"""
        search_query = f"{source_name} {' '.join(keywords[:2])} 2024 2025 geomarketing"
        
        payload = {
            'model': 'claude-sonnet-4-6',
            'max_tokens': 800,
            'tools': [{'type': 'web_search_20250305', 'name': 'web_search'}],
            'messages': [{
                'role': 'user',
                'content': f'Finde 2-3 aktuelle News zu "{search_query}" für Geomarketing/Standortplanung relevant. Gib mir Titel, URL-Beschreibung, Datum und 2-3 Stichwörter pro Artikel.'
            }]
        }
        
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            articles = []
            for content_block in data.get('content', []):
                if content_block.get('type') == 'text':
                    text = content_block.get('text', '')
                    if any(kw in text.lower() for kw in GEOMARKETING_KEYWORDS):
                        articles.append({
                            'source': source_name,
                            'title': text[:150],
                            'keywords': ', '.join(keywords[:2]),
                            'relevance': 'Hoch' if sum(text.lower().count(kw) for kw in GEOMARKETING_KEYWORDS) > 2 else 'Mittel',
                            'timestamp': datetime.now().isoformat()
                        })
            
            return articles[:2]
            
        except requests.exceptions.RequestException as e:
            print(f'❌ Fehler bei {source_name}: {str(e)}')
            return []
    
    def run_daily_scan(self):
        """Scanne alle Quellen nacheinander"""
        print(f'\n🔍 Starte tägliche Geomarketing-News-Suche um {datetime.now().strftime("%H:%M:%S")}')
        print('=' * 60)
        
        for source_name, keywords in SOURCES.items():
            print(f'\n📰 Durchsuche {source_name}…')
            articles = self.search_source(source_name, keywords)
            self.results.extend(articles)
            
            if articles:
                for article in articles:
                    print(f'  ✓ {article["title"][:60]}…')
            else:
                print(f'  - Keine relevanten Ergebnisse')
            
            time.sleep(0.5)
        
        print(f'\n✅ Scan abgeschlossen. {len(self.results)} relevante Artikel gefunden.')
        return self.results
    
    def save_to_json(self, filepath: str = None):
        """Speichere Ergebnisse als JSON"""
        if filepath is None:
            filepath = f"news/geomarketing_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'articles_count': len(self.results),
            'articles': self.results
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f'💾 Ergebnisse gespeichert: {filepath}')
        return filepath
    
    def print_report(self):
        """Drucke einen schönen Report in die Konsole"""
        print('\n' + '=' * 80)
        print('GEOMARKETING DAILY NEWS REPORT')
        print('=' * 80)
        print(f'Datum: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}')
        print(f'Quellen gescannt: {len(SOURCES)}')
        print(f'Artikel gefunden: {len(self.results)}\n')
        
        for article in self.results:
            print(f'📰 [{article["source"]}] {article["title"][:70]}...')
            print(f'   Keywords: {article["keywords"]} | Relevanz: {article["relevance"]}')
            print()
        
        print('=' * 80)


def main():
    """Hauptfunktion — starte den Scraper"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Geomarketing Daily News Aggregator')
    parser.add_argument('--output', default=None, help='JSON-Ausgabedatei')
    
    args = parser.parse_args()
    
    scraper = GeomarketingNewsScraper()
    scraper.run_daily_scan()
    
    if args.output:
        scraper.save_to_json(args.output)
    else:
        scraper.save_to_json()
    
    scraper.print_report()


if __name__ == '__main__':
    main()
