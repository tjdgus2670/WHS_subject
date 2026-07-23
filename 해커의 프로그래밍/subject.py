import re
import time

import requests
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


BASE_URL = 'http://board.nyan101.com'


def get_activity_data(max_pages=20, delay=0.3):
    """
    실제 사이트 구조에 맞춰 목록 페이지에서 post id를 수집하고,
    각 게시글의 /comments/{post_id} JSON을 읽어 사용자별 활동시간을 추정한다.
    """
    session = requests.Session()
    activity_rows = []

    for page_num in range(1, max_pages + 1):
        list_url = f'{BASE_URL}/list/{page_num}'
        try:
            page = session.get(list_url, timeout=20)
            page.raise_for_status()
        except Exception as e:
            print(f'페이지 수집 실패: {list_url} ({e})')
            break

        post_ids = re.findall(r'/post/(\d+)', page.text)
        if not post_ids:
            print(f'페이지 {page_num}에서 더 이상 게시글을 찾지 못했습니다.')
            break

        unique_post_ids = list(dict.fromkeys(post_ids))
        print(f'페이지 {page_num}: 게시글 {len(unique_post_ids)}개 수집')

        for post_id in unique_post_ids:
            comments_url = f'{BASE_URL}/comments/{post_id}'
            try:
                comments_res = session.get(comments_url, timeout=20)
                comments_res.raise_for_status()
                comments = comments_res.json()
            except Exception as e:
                print(f'댓글 수집 실패: {comments_url} ({e})')
                continue

            for item in comments:
                created_at = item.get('created_at')
                author_name = item.get('author_name')
                if created_at and author_name:
                    activity_rows.append({
                        'user': author_name,
                        'time_str': created_at,
                        'type': 'comment'
                    })

            time.sleep(delay)

        time.sleep(delay)

    return activity_rows


def process_and_visualize(activity_rows):
    if not activity_rows:
        print('수집된 데이터가 없습니다. 사이트 응답 또는 경로를 다시 확인하세요.')
        return

    df = pd.DataFrame(activity_rows)
    df['timestamp'] = pd.to_datetime(df['time_str'], format='%Y-%m-%d %H:%M', errors='coerce')
    df = df.dropna(subset=['timestamp']).copy()

    # 공개된 생성시각이 없으므로, 댓글 생성시각을 활동 시간의 대표 지표로 사용
    df['timestamp_kst'] = df['timestamp'].dt.tz_localize('Asia/Seoul')
    df['hour'] = df['timestamp_kst'].dt.hour

    user_hour_counts = (
        df.groupby(['user', 'hour']).size().reset_index(name='count')
    )
    user_hour_counts = user_hour_counts.sort_values(['user', 'hour'])

    plt.figure(figsize=(12, 9))

    user_ids = sorted(df['user'].unique())
    user_to_y = {user: i for i, user in enumerate(user_ids)}

    suspicious_users = []
    for user in user_ids:
        user_df = df[df['user'] == user]
        hour_counts = user_df['hour'].value_counts().sort_index()
        dominant_hour = hour_counts.idxmax()
        dominant_ratio = hour_counts.max() / len(user_df)

        # 비정상적 패턴: 특정 시간대에 과도하게 몰리거나, 심야에만 집중하는 경우
        if dominant_ratio >= 0.5 or dominant_hour in [0, 1, 2, 3, 4, 5]:
            suspicious_users.append(user)

        plt.scatter(user_df['hour'], [user_to_y[user]] * len(user_df), s=80, alpha=0.65)

    plt.yticks(range(len(user_ids)), user_ids)
    plt.xlabel('시간 (KST, 0~23시)')
    plt.ylabel('사용자 ID')
    plt.title('사용자별 활동 시간대 분포 (댓글 기준 활동 추정)')
    plt.xticks(range(0, 24))
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.tight_layout()
    plt.savefig('user_activity_chart.png', dpi=200)

    print('차트가 user_activity_chart.png 로 저장되었습니다.')
    if suspicious_users:
        print('잠재적 이상 사용자 후보:', ', '.join(sorted(set(suspicious_users))))


if __name__ == '__main__':
    raw_data = get_activity_data(max_pages=20, delay=0.3)
    process_and_visualize(raw_data)