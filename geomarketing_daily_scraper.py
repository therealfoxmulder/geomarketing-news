#!/usr/bin/env python3
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
    'DESTATIS': ['Standortanalyse', 'Demografie', 'Filialdichte'],
    'BBSR': ['ÖPNV', 'Leerstand', 'Nahversorgung'],
    'HDE': ['Filialschließung', 'Filialnetze', 'Mediareichweite'],
    'IW Köln': ['Demografie', 'Kita', 'Bevölkerungsrückgang'],
    'Reddit Geomarketing': ['Standortanalyse', 'Zentralität', 'Besucherfrequenzen'],
    'NIQ Reports': ['Kaufkraft', 'Zentralität', 'Ladeinfrastruktur']
}

GEOMARKETING_KEYWORDS = [
    'standortanalyse', 'filialdichte', 'öpnv', 'demografie', 'besucherfrequenzen',
    'kita', 'leerstand', 'kaufkraft', 'zentralität', 'filialschließung',
    'mixed-use', 'ladeinfrastruktur', 'nahversorgung', 'mediareichweite'
]

class GeomarketingNewsScraper:
    def __init__(self, anthropic_api_key: str = None):
        self.api_key = anthropic_api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set.")
        self.results = []
        self.base_url = 'https://api.anthropic.com/v1/messages'
        self.gmail_password = os.getenv('GMAIL_PASSWORD', '')
        
    def search_source(self, source_name: str, keywords: List[str]) -> List[Dict]:
        search_query = f"{source_name} {' '.join(keywords[:2])} 2024 2025"
        
        payload = {
            'model': 'claude-sonnet-4-6',
            'max_tokens': 800,
            'tools': [{'type': 'web_search_20250305', 'name': 'web_search'}],
            'messages': [{
                'role': 'user',
                'content': f'Finde 2-3 aktuelle News zu "{search_query}". Gib mir Titel und 2-3 Stichwörter pro Artikel.'
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
            
        except Exception as e:
            print(f'❌ Fehler bei {source_name}: {str(e)}')
            return []
    
    def run_daily_scan(self):
        print(f'\n🔍 Starte tägliche Suche um {datetime.now().strftime("%H:%M:%S")}')
        print('=' * 60)
        
        for source_name, keywords in SOURCES.items():
            print(f'\n📰 Durchsuche {source_name}…')
            articles = self.search_source(source_name, keywords)
            self.results.extend(articles)
            
            if articles:
                for article in articles:
                    print(f'  ✓ {article["title"][:60]}…')
            else:
                print(f'  - Keine Ergebnisse')
            
            time.sleep(0.5)
        
        print(f'\n✅ {len(self.results)} Artikel gefunden.')
        return self.results
    
    def save_to_json(self, filepath: str = None):
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
        
        print(f'💾 Gespeichert: {filepath}')
        return filepath
    
    def send_email(self, to_email: str):
        if not self.gmail_password:
            print('⚠️ GMAIL_PASSWORD nicht gesetzt.')
            return
        
        try:
            gmail_user = 'carstenbuchart@gmail.com'
            subject = f"Geomarketing Daily News - {datetime.now().strftime('%d.%m.%Y')}"
            
            html_content = f"""
            <html>
              <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #0b2540;">Geomarketing Daily News</h2>
                <p><strong>Datum:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                <p><strong>Quellen gescannt:</strong> {len(SOURCES)}</p>
                <p><strong>Artikel gefunden:</strong> {len(self.results)}</p>
                
                <hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">
                
                <h3 style="color: #0b2540;">Artikel</h3>
            """
            
            if self.results:
                html_content += '<ul style="line-height: 1.8;">'
                for article in self.results:
                    html_content += f"""
                      <li>
                        <strong>{article['source']}</strong><br>
                        {article['title']}<br>
                        <small style="color: #666;">Keywords: {article['keywords']} | Relevanz: {article['relevance']}</small>
                      </li>
                    """
                html_content += '</ul>'
            else:
                html_content += '<p style="color: #999;">Keine Artikel gefunden.</p>'
            
            html_content += """
                <hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">
                <p style="font-size: 12px; color: #999;">
                  Diese Email wurde automatisch von GitHub Actions generiert.<br>
                  NIQ Geomarketing | Carsten Buchart
                </p>
              </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = gmail_user
            msg['To'] = to_email
            msg.attach(MIMEText(html_content, 'html'))
            
            print(f'📧 Versuche Email zu versenden an {to_email}...')
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
                server.login(gmail_user, self.gmail_password)
                server.send_message(msg)
            
            print(f'✅ Email erfolgreich versendet an {to_email}')
            
        except smtplib.SMTPAuthenticationError:
            print('❌ Gmail-Login fehlgeschlagen. Überprüfe dein App-Passwort.')
        except smtplib.SMTPException as e:
            print(f'❌ SMTP-Fehler: {str(e)}')
        except Exception as e:
            print(f'❌ Fehler beim Email-Versand: {str(e)}')


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Geomarketing Daily News Aggregator')
    parser.add_argument('--output', default=None, help='JSON-Ausgabedatei')
    parser.add_argument('--email', default=None, help='Email-Adresse für Versand')
    
    args = parser.parse_args()
    
    scraper = GeomarketingNewsScraper()
    scraper.run_daily_scan()
    
    if args.output:
        scraper.save_to_json(args.output)
    else:
        scraper.save_to_json()
    
    if args.email:
        scraper.send_email(args.email)
    
    print('\n' + '=' * 80)
    print('BERICHT ABGESCHLOSSEN')
    print('=' * 80)


if __name__ == '__main__':
    main()
