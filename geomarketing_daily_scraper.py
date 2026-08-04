#!/usr/bin/env python3
"""
Geomarketing Daily News Aggregator
Lädt täglich um 8 Uhr Geomarketing-relevante News von definierten Quellen
Fasst zusammen und sendet per Email/Slack oder speichert lokal
"""

import json
import os
from datetime import datetime
from typing import List, Dict
import requests
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
                'content': f'Finde 2-3 aktuelle News zu "{search_query}" für Geomarketing/Standortplanung relevant. Gib mir Titel, URL-Beschreibung, Datum und ein 2-3 Stichwörter pro Artikel.'
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
    
    def generate_summary(self) -> str:
        """Generiere eine Zusammenfassung der Ergebnisse"""
        if not self.results:
            return 'Keine neuen Geomarketing-News heute verfügbar.'
        
        payload = {
            'model': 'claude-sonnet-4-6',
            'max_tokens': 400,
            'messages': [{
                'role': 'user',
                'content': f"""Fasse diese Geomarketing-News-Artikel in 3-4 Sätzen zusammen.
                Focus: Welche Trends sehen wir? Welche Branchen (Finance, Retail, Public Sector) sind betroffen?
                
                Artikel:
                {json.dumps(self.results, indent=2, ensure_ascii=False)}
                
                Antworte auf Deutsch, prägnant, keine Floskeln."""
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
            
            for content_block in data.get('content', []):
                if content_block.get('type') == 'text':
                    return content_block.get('text', 'Zusammenfassung konnte nicht generiert werden.')
        except requests.exceptions.RequestException as e:
            print(f'❌ Fehler bei Zusammenfassung: {str(e)}')
        
        return 'Zusammenfassung nicht verfügbar.'
    
    def save_to_json(self, filepath: str = None):
        """Speichere Ergebnisse als JSON"""
        if filepath is None:
            filepath = f"geomarketing_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'articles_count': len(self.results),
            'summary': self.generate_summary(),
            'articles': self.results
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f'💾 Ergebnisse gespeichert: {filepath}')
        return filepath
    
    def send_email(self, to_email: str, smtp_config: Dict):
        """Sende Zusammenfassung per Email"""
        summary = self.generate_summary()
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Geomarketing Daily News - {datetime.now().strftime('%d.%m.%Y')}"
        msg['From'] = smtp_config['from_email']
        msg['To'] = to_email
        
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Geomarketing Daily News</h2>
            <p><strong>Datum:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
            
            <h3>Zusammenfassung</h3>
            <p>{summary}</p>
            
            <h3>Artikel ({len(self.results)})</h3>
            <ul>
        """
        
        for article in self.results:
            html += f"""
              <li>
                <strong>{article['source']}:</strong> {article['title']}
                <br/><small>Keywords: {article['keywords']} | Relevanz: {article['relevance']}</small>
              </li>
            """
        
        html += """
            </ul>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        try:
            with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
                if smtp_config.get('use_tls'):
                    server.starttls()
                server.login(smtp_config['username'], smtp_config['password'])
                server.send_message(msg)
            print(f'📧 Email versendet an {to_email}')
        except smtplib.SMTPException as e:
            print(f'❌ Email-Fehler: {str(e)}')
    
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
        
        print('ZUSAMMENFASSUNG')
        print('-' * 80)
        print(self.generate_summary())
        print('=' * 80)


def main():
    """Hauptfunktion — starte den Scraper"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Geomarketing Daily News Aggregator')
    parser.add_argument('--api-key', default=None, help='Anthropic API Key (default: ANTHROPIC_API_KEY env var)')
    parser.add_argument('--output', default=None, help='JSON-Ausgabedatei')
    parser.add_argument('--email-to', default=None, help='Email-Adresse für Report')
    parser.add_argument('--smtp-config', default=None, help='SMTP-Config JSON-Datei')
    
    args = parser.parse_args()
    
    scraper = GeomarketingNewsScraper(api_key=args.api_key)
    scraper.run_daily_scan()
    
    if args.output:
        scraper.save_to_json(args.output)
    else:
        scraper.save_to_json()
    
    scraper.print_report()
    
    if args.email_to and args.smtp_config:
        with open(args.smtp_config, 'r') as f:
            smtp_config = json.load(f)
        scraper.send_email(args.email_to, smtp_config)


if __name__ == '__main__':
    main()
