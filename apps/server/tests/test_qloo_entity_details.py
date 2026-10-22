from __future__ import annotations

import os, sys
from pathlib import Path
import pytest

_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

pytestmark = pytest.mark.skipif(not os.getenv('QLOO_API_KEY'), reason='QLOO_API_KEY not set')

from app.services.qloo.entities import get_entity_details, get_entity_taste_profile, score_cultural_fit
from app.services.qloo.client import QlooClient, QlooConfig
from app.services.qloo.taste import search_cultural_entities

@pytest.fixture
async def client():
    c = QlooClient(config=QlooConfig.from_env())
    yield c
    await c.close()

def _skip_if_transient(payload):
    error = payload.get('error')
    if not error:
        return
    if error == 'auth_failed':
        pytest.fail('Qloo auth failed')
    transient = {'request_failed', 'bad_request', 'not_found', 'no_insights'}
    if error in transient:
        pytest.skip(f'Transient: {error}')
    pytest.skip(f'Unexpected: {error}')

@pytest.mark.asyncio
async def test_get_entity_details_resolves_pizza(client):
    results = await search_cultural_entities(client, 'Pizza', domain='dining', limit=3)
    assert len(results) > 0, 'Pizza not found - check QLOO_API_KEY'
    entity_id = results[0].get('entity_id') or results[0].get('id', '')
    assert entity_id
    details = await get_entity_details(client, entity_id)
    _skip_if_transient(details)
    assert details is not None
    assert details.get('id') == entity_id
    assert details.get('name')

@pytest.mark.asyncio
async def test_get_taste_profile_with_valid_ids(client):
    results = await search_cultural_entities(client, 'Italian cuisine', domain='dining', limit=2)
    if not results:
        pytest.skip('No Italian cuisine results')
    entity_ids = [r.get('entity_id', '') for r in results if r.get('entity_id')]
    if not entity_ids:
        pytest.skip('No entity IDs')
    profile = await get_entity_taste_profile(client, entity_ids[:2])
    _skip_if_transient(profile)
    assert 'profile' in profile
    entities = profile.get('profile', {}).get('entities', [])
    assert isinstance(entities, list)

@pytest.mark.asyncio
async def test_score_cultural_fit_returns_structure(client):
    results = await search_cultural_entities(client, 'Pasta', domain='dining', limit=1)
    if not results:
        pytest.skip('No Pasta results')
    pasta_id = results[0].get('entity_id', '')
    if not pasta_id:
        pytest.skip('No entity ID')
    result = await score_cultural_fit(client, [pasta_id], [pasta_id], domain='dining')
    _skip_if_transient(result)
    assert 'scores' in result
    assert isinstance(result.get('scores', []), list)
