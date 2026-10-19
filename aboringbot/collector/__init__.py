"""Collectors: one module per public source. Each returns the same normalized structure:

{"source": str,
 "clubs": {club_id: name},
 "matches": [{id, round, date, home, away, hg, ag, url}],
 "players": {player_id: {name, dob, birth_year, position, club}},
 "apps": [{match, player, club, started, minutes, goals, assists}]}
"""
