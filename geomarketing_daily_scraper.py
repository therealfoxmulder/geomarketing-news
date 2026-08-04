#!/usr/bin/env python3
import json
import os
from datetime import datetime
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SOURCES = {
    'DESTATIS': {
        'url': 'https://www.destatis.de/DE/Themen/Branchen-Unternehmen/Einzelhandel/_inhalt.html',
        'keywords': ['standortanalyse', 'filialdichte', 'einzelhandel', 'demografie', 'kommunal']
    },
    'IW Köln': {
        'url': 'https://www.iwkoeln.de/presse.html',
        'keywords': ['demografie', 'kita', 'bevölkerung', 'standort', 'kommunal']
    },
    'BBSR': {
        'url': 'https://www.bbsr.bund.de/BBSR/DE/forschung/forschungsthemen/stadt-und-raumordnung/forschungsthemen-node.html',
        'keywords': ['leerstand', 'öpnv', 'nahversorgung', 'infrastruktur', 'kommunal']
    },
    'Einzelhandelsverband': {
        'url': 'https://www.einzelhandelsverband.de/presse',
        'keywords': ['filialschließung', 'einzelhandel', 'expansion', 'standort', 'kommunal']
    },
    'ifh Köln': {
        'url': 'https://www.ifh-koeln.de/news',
        'keywords': ['einzelhandel', 'standort', 'filialnetzwerk', 'kaufkraft', 'kommunal']
    },
    'Stadt+Land': {
        'url': 'https://www.stadt-land.de/news',
        'keywords': ['stadtentwicklung', 'mixed-use', 'nahversorgung', 'standort', 'kommunal']
    },
    'Regiodata': {
        'url': 'https://www.regiodata.eu/de/news-blog',
        'keywords': ['geodaten', 'standortanalyse', 'demografie', 'kaufkraft', 'kommunal']
    },
    'mbi geodata': {
        'url': 'https://www.mbi-geodata.de/news',
        'keywords': ['geodaten', 'geomarketing', 'standort', 'zentralität', 'kommunal']
    }
}

GEOMARKETING_KEYWORDS = [
    'standortanalyse', 'filialdichte', 'öpnv', 'demografie', 'besucherfrequenzen',
    'kita', 'leerstand', 'kaufkraft', 'zentralität', 'filialschließung',
    'mixed-use', 'ladeinfrastruktur', 'nahversorgung', 'mediareichweite',
    'einzelhandel', 'bevölkerung', 'infrastruktur', 'expansion', 'geodaten',
    'geomarketing', 'filialnetzwerk', 'stadtentwicklung', 'kommunal'
]

class GeomarketingNewsScraper:
    def __init__(self, anthropic_api_key: str = None, debug: bool = False):
        self.results = []
        self.debug = debug
        self.gmail_password = os.getenv('GMAIL_PASSWORD', '')
        
    def scrape_source(self, source_name: str, source_config: Dict) -> List[Dict]:
        url = source_config['url']
        keywords = source_config['keywords']
        
        if self.debug:
            print(f'\n   🔗 Scrape: {url}')
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            if self.debug:
                print(f'   📊 Status: {response.status_code}')
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            articles = []
            
            # Suche nach News/Artikel-Containern
            for link in soup.find_all('a', href=True):
                link_text = link.get_text(strip=True)
                link_url = link.get('href', '')
                
                # Filtere nach Relevanz
                if any(kw in link_text.lower() for kw in GEOMARKETING_KEYWORDS):
                    if len(link_text) > 10:  # Ignoriere zu kurze Texte
                        articles.append({
                            'source': source_name,
                            'title': link_text[:150],
                            'url': link_url if link_url.startswith('http') else url.split('/')[0] + '//' + url.split('/')[2] + link_url,
                            'keywords': ', '.join(keywords[:2]),
                            'relevance': 'Hoch' if sum(link_text.lower().count(kw) for kw in GEOMARKETING_KEYWORDS) > 1 else 'Mittel',
                            'timestamp': datetime.now().isoformat()
                        })
            
            if self.debug:
                print(f'   ✅ {len(articles)} Artikel gefunden')
            
            return articles[:3]
            
        except Exception as e:
            print(f'❌ Fehler bei {source_name}: {str(e)}')
            return []
    
    def run_daily_scan(self):
        print(f'\n🔍 Starte tägliche Suche um {datetime.now().strftime("%H:%M:%S")}')
        print('=' * 80)
        
        for source_name, source_config in SOURCES.items():
            print(f'\n📰 Durchsuche {source_name}…')
            articles = self.scrape_source(source_name, source_config)
            self.results.extend(articles)
            
            if articles:
                for article in articles:
                    print(f'  ✓ {article["title"][:60]}…')
            else:
                print(f'  - Keine Ergebnisse')
            
            time.sleep(1)
        
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
            
            html_content = '<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">'
            html_content += '<h2 style="color: #0b2540;">Geomarketing Daily News</h2>'
            html_content += f'<p><strong>Datum:</strong> {datetime.now().strftime("%d.%m.%Y %H:%M")}</p>'
            html_content += f'<p><strong>Quellen gescannt:</strong> {len(SOURCES)}</p>'
            html_content += f'<p><strong>Artikel gefunden:</strong> {len(self.results)}</p>'
            html_content += '<hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">'
            html_content += '<h3 style="color: #0b2540;">Artikel</h3>'
            
            if self.results:
                html_content += '<ul style="line-height: 1.8;">'
                for article in self.results:
                    html_content += '<li>'
                    html_content += f'<strong>{article["source"]}</strong><br>'
                    html_content += f'{article["title"]}<br>'
                    if 'url' in article and article['url']:
                        html_content += f'<a href="{article["url"]}" style="color: #E8672A;">Link</a><br>'
                    html_content += f'<small style="color: #666;">Relevanz: {article["relevance"]}</small>'
                    html_content += '</li>'
                html_content += '</ul>'
            else:
                html_content += '<p style="color: #999;">Keine Artikel gefunden.</p>'
            
            html_content += '<hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">'
            html_content += '<p style="font-size: 12px; color: #999;">'
            html_content += 'Diese Email wurde automatisch von GitHub Actions generiert.<br>'
            html_content += 'NIQ Geomarketing | Carsten Buchart'
            html_content += '</p></body></html>'
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = gmail_user
            msg['To'] = to_email
            msg.attach(MIMEText(html_content, 'html'))
            
            print(f'📧 Email versenden an {to_email}…')
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
                server.login(gmail_user, self.gmail_password)
                server.send_message(msg)
            
            print(f'✅ Email versendet')
            
        except Exception as e:
            print(f'❌ Email-Fehler: {str(e)}')


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Geomarketing Daily News Aggregator')
    parser.add_argument('--output', default=None, help='JSON-Ausgabedatei')
    parser.add_argument('--email', default=None, help='Email-Adresse für Versand')
    parser.add_argument('--debug', action='store_true', help='Debug-Modus')
    
    args = parser.parse_args()
    
    scraper = GeomarketingNewsScraper(debug=args.debug)
    scraper.run_daily_scan()
    
    if args.output:
        scraper.save_to_json(args.output)
    else:
        scraper.save_to_json()
    
    if args.email:
        scraper.send_email(args.email)
    
    print('\n' + '=' * 80)
    print('BERICHT ABGESCHLOSSEN - 8 Quellen gescannt')
    print('=' * 80)


if __name__ == '__main__':
    main()
