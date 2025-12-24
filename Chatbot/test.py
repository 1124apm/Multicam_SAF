import json
import random
import pandas as pd
import numpy as np

고칠점: 결과가 두 번씩 나옴, 경로 이상함


# 데이터 로드
with open('final_team_data3.json', 'r', encoding='utf-8') as f:
    teams = json.load(f)

universal_needs = {
    "공격성": ["화끈한 공격력", "공격 위주의 전술", "물러서지 않는 플레이", "득점력이 높은"],
    "자본력": ["재정이 탄탄한", "투자를 많이 하는", "빅클럽", "자본력이 빵빵한"],
    "전통": ["역사가 깊은", "전통 있는 명문", "근본 있는", "헤리티지가 느껴지는"],
    "언더독": ["반란을 꿈꾸는", "약팀의 반격", "스토리가 있는", "도전적인"],
    "스타성": ["스타 플레이어가 많은", "화려한 인지도의", "팬덤이 거대한"]
}

def generate_universal_test_data(num=50):
    dataset = []
    
    for _ in range(num):
        # 1. 포괄적 카테고리 하나 선택
        category = random.choice(list(universal_needs.keys()))
        vibe = random.choice(universal_needs[category])
        
        # 2. 질문 생성 (종목 이름을 빼서 범용성 확보)
        query = f"저는 {vibe} 팀을 응원하고 싶은데, 저랑 잘 맞는 팀이 있을까요?"
        
        for idx, team in enumerate(teams):
            # S_semantic: 키워드 매칭 (가중치 조절 가능)
            match_count = sum(1 for tag in team['style_tags'] if tag in vibe)
            s_semantic = min(1.0, match_count * 0.5) 

            # S_relational: 수치 데이터 반영
            # (카테고리에 맞는 score 항목을 매칭해서 계산)
            score_key_map = {"공격성": "attack_style", "자본력": "money", "전통": "tradition", "언더독": "underdog_feel", "스타성": "star_power"}
            target_score_key = score_key_map[category]
            s_relational = team['scores'][target_score_key] / 10.0 # 10점 만점 기준 정규화
            
            # W_id: 가중치 적용
            w_id = 0.9 + (team['scores']['underdog_feel'] / 50.0)
            
            # 최종 점수 계산 (태그 0.4 : 수치 0.6 비중)
            final_score = (0.4 * s_semantic + 0.6 * s_relational) * w_id
            # ---------------------------------------

            dataset.append({
                "성향_카테고리": category,
                "사용자_질문": query,
                "비교_대상_팀": team['team_name'],
                "유사도_점수": round(min(0.99, final_score), 4)
            })
            
    return pd.DataFrame(dataset)

# 실행 및 저장
df_master = generate_universal_test_data(100)
df_master.to_csv("범용_규격_테스트_결과.csv", index=False, encoding='utf-8-sig')