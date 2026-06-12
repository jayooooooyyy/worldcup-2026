# API-Football 数据抓取报告

## 数据源

- Provider：API-Football / API-Sports
- Host：v3.football.api-sports.io
- League：World Cup，league id = 1
- API key：未写入项目文件；运行脚本时通过环境变量 `API_FOOTBALL_KEY` 读取

## 已抓取数据

- Seasons requested：2010, 2014, 2018, 2022, 2026
- Fixtures rows：64
- Teams rows：32
- Standings rows：32
- Top players rows：80

## 输出文件

- `data/external/api_football/api_football_world_cup_fixtures.csv`
- `data/external/api_football/api_football_world_cup_teams.csv`
- `data/external/api_football/api_football_world_cup_standings.csv`
- `data/external/api_football/api_football_world_cup_top_players.csv`
- `data/external/api_football/raw`：原始 JSON 响应

## 重要限制

- 当前 Free plan 无法访问 World Cup 2026 season，接口提示可访问范围为 2022 到 2024。
- World Cup 的 injuries coverage 为 false，因此伤病接口目前没有可用世界杯伤病数据。
- 当前脚本先抓历史世界杯数据，用于模型增强、回测和未来数据结构对接。

## API 错误或限制

- `/fixtures` {'league': 1, 'season': 2010}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/teams` {'league': 1, 'season': 2010}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/standings` {'league': 1, 'season': 2010}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topscorers` {'league': 1, 'season': 2010}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topassists` {'league': 1, 'season': 2010}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topyellowcards` {'league': 1, 'season': 2010}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topredcards` {'league': 1, 'season': 2010}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/fixtures` {'league': 1, 'season': 2014}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/teams` {'league': 1, 'season': 2014}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/standings` {'league': 1, 'season': 2014}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topscorers` {'league': 1, 'season': 2014}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topassists` {'league': 1, 'season': 2014}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topyellowcards` {'league': 1, 'season': 2014}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topredcards` {'league': 1, 'season': 2014}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/fixtures` {'league': 1, 'season': 2018}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/teams` {'league': 1, 'season': 2018}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/standings` {'league': 1, 'season': 2018}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topscorers` {'league': 1, 'season': 2018}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topassists` {'league': 1, 'season': 2018}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topyellowcards` {'league': 1, 'season': 2018}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topredcards` {'league': 1, 'season': 2018}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/fixtures` {'league': 1, 'season': 2026}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/teams` {'league': 1, 'season': 2026}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/standings` {'league': 1, 'season': 2026}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topscorers` {'league': 1, 'season': 2026}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topassists` {'league': 1, 'season': 2026}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topyellowcards` {'league': 1, 'season': 2026}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
- `/players/topredcards` {'league': 1, 'season': 2026}：{'plan': 'Free plans do not have access to this season, try from 2022 to 2024.'}
