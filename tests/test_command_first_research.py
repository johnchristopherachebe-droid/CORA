from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
backend = (ROOT / "main.py").read_text()
ui = (ROOT / "public" / "index.html").read_text()

def test_unified_search_endpoint_collects_web_news_and_video_concurrently():
    assert '@app.get("/web/unified-search")' in backend
    assert 'pool.submit(web_lookup)' in backend
    assert 'pool.submit(news_lookup)' in backend
    assert 'pool.submit(video_lookup)' in backend
    assert 'youtube-nocookie.com/embed/' in backend

def test_command_first_research_ui_has_tabs_and_auto_search_intent():
    assert 'function renderUnifiedResearch(data)' in ui
    assert 'data-research-tab' in ui
    assert 'research-tabpanel' in ui
    assert 'runUnifiedSearch(searchIntent[1])' in ui
    assert '#webSearchBtn,#webResearchBtn{display:none!important}' in ui
    assert '#commandForm>button[type="submit"]{display:none!important}' in ui
    assert 'https://www.youtube-nocookie.com/embed/' in ui
