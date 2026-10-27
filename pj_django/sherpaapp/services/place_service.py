import requests
from django.conf import settings


KAKAO_URL = 'https://dapi.kakao.com/v2/local/search/keyword.json'

# 카카오 장소 분류에서 "여행 장소"로 쓰면 안 되는 것들
JUNK_KINDS = (
    '주차장', '부동산', '주거시설', '아파트', '도시형생활주택',
    '교통,수송', '공인중개', '인테리어', '건축',
)

MALL_KINDS = ('쇼핑몰', '백화점', '아울렛')

# '랜드마크'처럼 뜻이 넓은 컨셉은 그 글자 그대로 검색하면
# 이름에 '랜드마크'가 들어간 주차장/아파트가 나온다.
# 그래서 실제 관광명소(AT4)를 찾도록 검색어를 바꿔서 쓴다.
CONCEPT_QUERIES = {
    '랜드마크': (
        # (검색어, 카카오 분류 코드, 이 분류만 허용할 때의 분류 이름)
        ('관광명소', 'AT4', None),
        ('대형 쇼핑몰', '', MALL_KINDS),
    ),
    '역사': (('역사 유적지', 'AT4', None),),
    '전통문화': (('전통 문화 명소', 'AT4', None),),
}


def is_junk_kind(category_name):
    name = category_name or ''

    return any(word in name for word in JUNK_KINDS)


def concept_plan(concept, size):
    """컨셉 하나를 (검색어, 분류코드, 허용분류, 개수) 목록으로 바꾼다."""
    specs = CONCEPT_QUERIES.get(concept)

    if not specs:
        return None

    if len(specs) == 1:
        q, group, allow = specs[0]
        return [(q, group, allow, size)]

    extra = max(1, size // 4) if size >= 3 else 0
    plan = []

    for i, (q, group, allow) in enumerate(specs):
        count = size - extra if i == 0 else extra

        if count > 0:
            plan.append((q, group, allow, count))

    return plan


def kakao_documents(query, size, group='', **extra):
    headers = {
        'Authorization': f'KakaoAK {settings.KAKAO_REST_API_KEY}'
    }

    params = {
        'query': query,
        'size': max(1, min(size, 15)),
    }

    if group:
        params['category_group_code'] = group

    params.update(extra)

    response = requests.get(
        KAKAO_URL,
        headers=headers,
        params=params,
        timeout=8
    )

    response.raise_for_status()

    return response.json().get('documents', [])


def to_place(item, category):
    return {
        'name': item.get('place_name'),
        'address':
            item.get('road_address_name')
            or item.get('address_name'),
        'lat': item.get('y'),
        'lon': item.get('x'),
        'category': category,
        'phone': item.get('phone'),
        'place_url': item.get('place_url'),
        'kakao_group': item.get('category_group_code') or '',
        'kakao_category': item.get('category_name') or '',
    }


def search_places(region, category, size=10):

    plan = concept_plan(category, size)

    # 일반 검색 (카페, 맛집, 숙소 이름 등)
    if not plan:
        plan = [(category, '', None, size)]
        expanded = False
    else:
        expanded = True

    places = []
    seen = set()

    for query, group, allow, count in plan:

        try:
            documents = kakao_documents(
                f'{region} {query}',
                count + (5 if expanded else 0),
                group
            )
        except Exception:
            # 확장 검색 중 하나가 실패해도 나머지로 계속
            if len(plan) == 1:
                raise
            continue

        added = 0

        for item in documents:

            kind = item.get('category_name') or ''

            if expanded and is_junk_kind(kind):
                continue

            if allow and not any(w in kind for w in allow):
                continue

            key = (item.get('place_name'), item.get('address_name'))

            if key in seen:
                continue

            seen.add(key)
            places.append(to_place(item, category))
            added += 1

            if added >= count:
                break

    # 확장 검색 결과가 하나도 없으면 원래 말 그대로 한 번 더 찾는다
    if expanded and not places:
        for item in kakao_documents(f'{region} {category}', size):
            if not is_junk_kind(item.get('category_name')):
                places.append(to_place(item, category))

    return places
