import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import os
import re
from urllib.parse import unquote

# --- 설정 및 데이터 ---

# 크롤링할 대상 URL 리스트 (여기에 원하는 링크들을 추가하세요)
TARGET_URLS = [
    "https://namu.wiki/w/%ED%8F%AC%EB%AE%AC%EB%9F%AC%201/2025%EC%8B%9C%EC%A6%8C",
    "https://namu.wiki/w/%ED%8F%AC%EB%AE%AC%EB%9F%AC%201/2024%EC%8B%9C%EC%A6%8C",
    "https://namu.wiki/w/%ED%8F%AC%EB%AE%AC%EB%9F%AC%201/2023%EC%8B%9C%EC%A6%8C",
    "https://namu.wiki/w/%ED%8F%AC%EB%AE%AC%EB%9F%AC%201/2022%EC%8B%9C%EC%A6%8C",
    "https://namu.wiki/w/%ED%8F%AC%EB%AE%AC%EB%9F%AC%201/2021%EC%8B%9C%EC%A6%8C",
    "https://namu.wiki/w/%ED%8F%AC%EB%AE%AC%EB%9F%AC%201/2020%EC%8B%9C%EC%A6%8C"
]

# 팀별 키워드 정의 (한국어 및 영어)
TEAM_KEYWORDS = {
    "Scuderia_Ferrari": ["페라리", "Ferrari", "SF-24"],
    "Red_Bull_Racing": ["레드불", "Red Bull", "RB20"],
    "McLaren": ["맥라렌", "McLaren", "MCL38"],
    "Alpine_F1_Team": ["알핀", "Alpine", "A524", "르노", "Renault", "RNR26"],
    "Haas_F1_Team": ["하스", "Haas", "VF-24"],
    "Sauber_Motorsport": ["자우버", "Sauber", "Kick Sauber", "C44", "알파 로메오", "Alfa Romeo", "Stake"],
    "Aston_Martin_in_Formula_One": ["애스턴 마틴", "애스턴마틴", "Aston Martin", "레이싱 포인트", "AMR24"],
    "Mercedes-Benz_in_Formula_One": ["메르세데스", "벤츠", "Mercedes", "W15"],
    "Williams_Racing": ["윌리엄스", "Williams", "FW46"],
    "Racing_Bulls": ["레이싱 불스", "Racing Bulls", "VCARB", "RB", "알파 타우리", "Alpha Tauri", "ATR26"]
}

OUTPUT_DIR = "(KOR)F1_namuwiki_season"


async def crawl_namuwiki_content(url):
    """
    주어진 URL에서 본문 텍스트를 추출하여 반환합니다.
    제목, 표, 이미지, 동영상, 링크 텍스트 등을 제외합니다.
    """
    print(f"🔄 크롤링 시작: {url}")
    extracted_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 봇 탐지 회피를 위한 컨텍스트 설정
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            response = await page.goto(url, timeout=60000)
            if response is None or response.status >= 400:
                print(f"❌ HTTP 요청 실패: {response.status if response else 'N/A'} - {url}")
                await browser.close()
                return None
            
            # 본문 로딩 대기 (개요 등 주요 헤더가 뜰 때까지)
            try:
                await page.wait_for_selector('h2', state='attached', timeout=30000)
            except Exception:
                print(f"⚠️ H2 태그를 찾는데 시간이 오래 걸리거나 실패했습니다. 계속 진행합니다.")

            html_content = await page.content()
            await browser.close() 
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 본문 컨테이너 찾기
            # 나무위키 클래스명은 자주 바뀌므로, 문서 제목(h1)을 찾고 그 부모 혹은 형제 노드를 탐색하는 것이 안전할 수 있으나,
            # 현재 알려진 main container 클래스를 먼저 시도하고, 없으면 article 태그 등을 찾습니다.
            content = soup.find('div', class_='NMmqIPVM _61W7Avfw')
            
            if not content:
                # 대체 탐색: article 태그 시도
                content = soup.find('article')
            
            if not content:
                print(f"❌ 문서의 메인 콘텐츠 영역을 찾을 수 없습니다: {url}")
                return None
            
            # --- 제외 작업 (Decompose) ---
            # --- 제외 작업 (Decompose) ---
            # 1. 목차(TOC), 표(table), 이미지(img, figure, video), 각주(sup, span.wiki-fn-content) 제거
            # nav, aside 등 도 제거
            for tag in content.find_all(['table', 'img', 'video', 'figure', 'iframe', 'canvas', 'nav', 'aside', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                if not tag.name:
                    continue
                    
                # div의 경우 특정 클래스(목차 등)만 제거
                if tag.name == 'div':
                    classes = tag.get('class', [])
                    if classes and ('wiki-macro-toc' in classes or 'toc' in classes):
                        tag.decompose()
                # 헤더 태그는 제목이므로 제외 (사용자 요청: 제목 제외)
                elif tag.name.startswith('h'):
                    tag.decompose()
                else: 
                    tag.decompose()
            
            # 각주 및 편집 버튼 제거
            for tag in content.find_all(class_=['wiki-fn-content', 'wiki-edit-date', 'wiki-category']):
                tag.decompose()
            for tag in content.find_all('a', text=re.compile(r'\[편집\]')):
                tag.decompose()

            # --- 텍스트 추출 ---
            # Namuwiki 본문 텍스트는 주로 class='IBdgNaCn' 인 div 또는 li 태그에 있음.
            # 중복 방지를 위해 specific selector 사용.
            paragraphs = content.select('div.IBdgNaCn, li')
            
            seen_texts = set()

            for p in paragraphs:
                # 링크(a 태그)는 unwrap하여 텍스트만 남김
                for a in p.find_all('a'):
                    a.unwrap()
                
                text = p.get_text(strip=True)
                
                # 정제 및 중복 필터링
                if not text:
                    continue
                if len(text) < 10: 
                    continue
                if text in seen_texts:
                    continue
                
                # 상위 문단이 잡히고 하위 문단이 또 잡히는 경우 방지 (포함 관계 확인 등은 복잡하므로 텍스트 중복으로 1차 방어)
                # 만약 "A B"가 있고 "A", "B"가 따로 잡히면?
                # IBdgNaCn 클래스는 보통 말단 문단에 붙으므로 중첩이 적음.
                
                seen_texts.add(text)
                extracted_data.append(text)

        except Exception as e:
            print(f"❌ 크롤링 중 예외 발생: {e} - {url}")
            return None

    return extracted_data


def classify_and_save(all_text_data):
    """
    수집된 텍스트 리스트를 순회하며 팀 키워드에 따라 분류하고 파일에 저장합니다.
    """
    # 팀별로 저장할 텍스트 버퍼
    team_buffers = {key: [] for key in TEAM_KEYWORDS.keys()}
    
    # 디렉토리 생성
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 순서 보장을 위해 List 사용. 중복 제거 여부는? 
    # 하나의 텍스트 청크가 여러 팀에 속할 수 있음 -> OK (User requirement: "각 팀별 txt에 넣어줘야 한다")
    # 하지만 텍스트 청크 자체의 중복(크롤링 단계에서 발생한)은 제거해야 함 (위에서 처리함).
    
    for text in all_text_data:
        matched_teams = set()
        
        # 키워드 매칭
        for team_key, keywords in TEAM_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    matched_teams.add(team_key)
                    # "가장 관련성이 높은 팀을 찾지 말고... 각각의 팀별 txt에 넣어줘야"
                    # -> break 하지 않고 계속 찾아서 multi-labeling?
                    # User: "한 링크의 내용을 무조건 한 팀의 파일에 넣어야 하는 건 아니야... 각각의 팀별 txt에 넣어줘야 한다는 걸 명심"
                    # This implies multi-classification is required if multiple keywords appear.
                    # My previous code did `break` inside the inner loop (keyword loop) but NOT the outer loop (team loop).
                    # `break` breaks `for kw in keywords`. It proceeds to next `team_key`.
                    # So it WAS multi-labeling correctly.
                    break 
        
        # 매칭된 모든 팀에 텍스트 추가
        if matched_teams:
            for team in matched_teams:
                # 간단한 중복 방지 (동일 파일 내 동일 텍스트)
                if text not in team_buffers[team]:
                    team_buffers[team].append(text)

        else:
            # (선택사항) 어떤 팀에도 속하지 않는 텍스트는 버리거나 별도 로그?
            # 현재 요구사항: "각 팀에 관한 내용만 팀 별 최종 결과물 txt파일에 넣어줘" -> 버림
            pass

    # 파일 쓰기
    for team_key, texts in team_buffers.items():
        if not texts:
            continue
            
        file_path = os.path.join(OUTPUT_DIR, f"{team_key}.txt")
        
        # 기존 파일 내용 확인 (중복 방지용)
        existing_content = ""
        file_exists = os.path.exists(file_path)
        
        if file_exists:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            except Exception:
                pass # 파일 읽기 실패 시 중복 체크 건너뜀 (그냥 append)

        mode = 'a' if file_exists else 'w'
        
        try:
            with open(file_path, mode, encoding='utf-8') as f:
                # 새 파일이면 헤더 작성
                if not file_exists:
                    f.write(f"팀 이름: {team_key}\n")
                    f.write("========== TEAM NARRATIVE DATA (Namuwiki) ==========\n")
                
                # 내용 추가 (중복 체크)
                append_count = 0
                for t in texts:
                    # 기존 파일에 텍스트가 없고 (혹은 너무 짧아 구분이 안되거나), 
                    # 현재 모으고 있는 existing_content에도 없어야 함.
                    # (단, existing_content가 너무 커지면 느려질 수 있으나 텍스트 파일 수준에선 OK)
                    if t.strip() not in existing_content:
                        f.write(t + "\n\n")
                        existing_content += t + "\n\n" # 같은 실행 루프 내 중복 방지 업데이트
                        append_count += 1
                
            if append_count > 0:
                print(f"✅ [{team_key}] {append_count}개 항목 추가 저장 완료: {file_path}")
            else:
                print(f"ℹ️ [{team_key}] 새로운 내용이 없어 저장하지 않았습니다.")
                
        except Exception as e:
            print(f"❌ 파일 저장 실패 {team_key}: {e}")


async def main_async():
    print("나무위키 F1 데이터 크롤링 및 분류를 시작합니다...\n")
    
    # 전체 URL에서 수집된 모든 텍스트 (순서 유지)
    all_collected_text = []

    for url in TARGET_URLS:
        data = await crawl_namuwiki_content(url)
        if data:
            all_collected_text.extend(data)
            
    print(f"\n총 {len(all_collected_text)}개의 텍스트 청크를 수집했습니다. 분류를 시작합니다...")
    
    classify_and_save(all_collected_text)
    
    print("\n모든 작업이 완료되었습니다.")

if __name__ == "__main__":
    asyncio.run(main_async())
