#!/usr/bin/env python3
"""
Geomarketing Daily News Aggregator - WITH EMAIL SUPPORT
Lädt täglich um 8 Uhr Geomarketing-relevante News von definierten Quellen
Sendet die Ergebnisse per Email
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
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Set it via environment variable or pass it directly.")
        self.results = []
        self.base_url = 'https://api.anthropic.com/v1/messages'
        self.gmail_password = os.getenv('GMAIL_PASSWORD', '')
        
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
    
    def send_email(self, to_email: str):
        """Sende Report per Gmail"""
        if not self.gmail_password:
            print('⚠️ GMAIL_PASSWORD nicht gesetzt. Email wird übersprungen.')
            return
        
        try:
            gmail_user = 'geomarketing-news@gmail.com'
            subject = f"Geomarketing Daily News - {datetime.now().strftime('%d.%m.%Y')}"
            
            html_content = f"""
            <html>
              <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <h2>Geomarketing Daily News</h2>
                <p><strong>Datum:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                
                <h3>Zusammenfassung</h3>
                <p>Gescannt: {len(SOURCES)} Quellen | Artikel gefunden: {len(self.results)}</p>
                
                <h3>Artikel</h3>
                <ul>
            """
            
            for article in self.results:
                html_content += f"""
                  <li>
                    <strong>{article['source']}:</strong> {article['title']}
                    <br/><small>Keywords: {article['keywords']} | Relevanz: {article['relevance']}</small>
                  </li>
                """
            
            html_content += """
                </ul>
                <hr>
                <p style="font-size: 12px; color: #666;">
                  Diese Email wurde automatisch von GitHub Actions generiert.
                </p>
              </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = gmail_user
            msg['To'] = to_email
            
            msg.attach(MIMEText(html_content, 'html'))
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
                server.login(gmail_user, self.gmail_password)
                server.send_message(msg)
            
            print(f'✅ Email versendet an {to_email}')
            
        except smtplib.SMTPAuthenticationError:
            print('❌ Gmail-Login fehlgeschlagen. Überprüfe App-Passwort.')
        except smtplib.SMTPException as e:
            print(f'❌ Email-Fehler: {str(e)}')
        except Exception as e:
            print(f'❌ Fehler beim Email-Versand: {str(e)}')
    
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
    parser.add_argument('--email', default=None, help='Email-Adresse für Report')
    
    args = parser.parse_args()
    
    scraper = GeomarketingNewsScraper()
    scraper.run_daily_scan()
    
    if args.output:
        scraper.save_to_json(args.output)
    else:
        scraper.save_to_json()
    
    if args.email:
        scraper.send_email(args.email)
    
    scraper.print_report()


if __name__ == '__main__':
    main()
