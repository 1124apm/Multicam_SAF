import requests
from bs4 import BeautifulSoup
import os
import time

def crawl_and_save_wikipedia_text(team_name_en, url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # 파일 저장 경로 및 이름 설정
    file_name = f"{team_name_en}_wiki_data.txt"
    output_dir = "(ENG)F1_Crawled_Data"
    os.makedirs(output_dir, exist_ok=True) # 폴더 없으면 생성

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() # HTTP 오류가 발생하면 예외 발생

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 핵심 콘텐츠 영역만 선택 (위키피디아 기준)
        content = soup.find(id="mw-content-text")
        if not content:
            return "핵심 콘텐츠 영역을 찾을 수 없습니다."

        # 노이즈 제거 (순수한 텍스트 품질 향상)
        # - 표 (테이블) 제거
        for table in content.find_all('table'):
            table.decompose()
        
        # - 각주, 링크 내부의 텍스트를 제거 (순수한 문단 텍스트만 남김)
        for sup in content.find_all('sup', class_='reference'):
            sup.decompose() # 각주 번호 제거

        # - 이미지 제거 (굳이 필요 없지만 안정성을 위해)
        for img in content.find_all('img'):
            img.decompose()
        
        extracted_text = []

        # 원하는 태그 (h1, h2, h3, p)에서 텍스트 추출
        for element in content.find_all(['h1', 'h2', 'h3', 'p']):
            
            # 태그 이름과 텍스트 내용을 분리하여 저장
            tag_name = element.name
            # .text로 텍스트를 추출하고, strip()으로 앞뒤 공백 제거
            text_content = element.text.strip()
            
            # 링크가 제거되지 않은 채 남아있거나 괄호 안의 짧은 텍스트는 무시
            if text_content and len(text_content) > 10:
                
                # h1, h2, h3은 제목임을 명확히 표시
                if tag_name in ['h1', 'h2', 'h3']:
                    extracted_text.append(f"\n[{tag_name.upper()}] {text_content}")
                else:
                    # 일반 문단 (p)의 경우
                    extracted_text.append(text_content)


        # 결과를 TXT 파일로 저장
        full_path = os.path.join(output_dir, file_name)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(f"URL: {url}\n\n")
            f.write("========== TEAM NARRATIVE DATA ==========\n")
            f.write('\n'.join(extracted_text))
            
        print(f"✅ [{team_name_en}] 데이터 크롤링 및 저장이 완료되었습니다: {full_path}")
        return full_path

    except requests.exceptions.RequestException as e:
        print(f"❌ [{team_name_en}] 크롤링 오류 발생: {e}")
        return None

# --- 실행 ---
f1_teams = {
    "Scuderia_Ferrari": "https://en.wikipedia.org/wiki/Scuderia_Ferrari",
    "Red_Bull_Racing": "https://en.wikipedia.org/wiki/Red_Bull_Racing",
    "McLaren": "https://en.wikipedia.org/wiki/McLaren",
    "Alpine_F1_Team": "https://en.wikipedia.org/wiki/Alpine_F1_Team?wprov=srpw1_0",
    "Haas_F1_Team": "https://en.wikipedia.org/wiki/Haas_F1_Team",
    "Sauber_Motorsport": "https://en.wikipedia.org/wiki/Sauber_Motorsport",
    "Aston_Martin_in_Formula_One": "https://en.wikipedia.org/wiki/Aston_Martin_in_Formula_One",
    "Mercedes-Benz_in_Formula_One": "https://en.wikipedia.org/wiki/Mercedes-Benz_in_Formula_One",
    "Williams_Racing": "https://en.wikipedia.org/wiki/Williams_Racing",
    "Racing_Bulls": "https://en.wikipedia.org/wiki/Racing_Bulls"
}

print("위키피디아 F1 팀 데이터 크롤링을 시작합니다...\n")

for team_name, url in f1_teams.items():
    crawl_and_save_wikipedia_text(team_name, url)
    time.sleep(2)
    
print("\n모든 팀에 대한 크롤링 작업이 완료되었습니다.")