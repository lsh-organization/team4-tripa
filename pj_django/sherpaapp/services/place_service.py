import requests
from django.conf import settings


def search_places(region, category, size=10):

    url = 'https://dapi.kakao.com/v2/local/search/keyword.json'

    headers = {
        'Authorization': f'KakaoAK {settings.KAKAO_REST_API_KEY}'
    }

    params = {
        'query': f'{region} {category}',
        'size': size
    }

    response = requests.get(
        url,
        headers=headers,
        params=params
    )

    response.raise_for_status()

    data = response.json()

    places = []

    for item in data.get('documents', []):

        places.append({
            'name': item.get('place_name'),
            'address':
                item.get('road_address_name')
                or item.get('address_name'),
            'lat': item.get('y'),
            'lon': item.get('x'),
            'category': category,
            'phone': item.get('phone'),
            'place_url': item.get('place_url'),
        })

    return places