from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import random
from functools import wraps

app = Flask(__name__)
app.secret_key = 'twoj_tajny_klucz_do_projektu'  # Zmień na własny klucz

# Dostępni użytkownicy (maksymalnie 6)
USERS = {
    'gracz1': 'haslo1',
    'gracz2': 'haslo2',
    'gracz3': 'haslo3',
    'gracz4': 'haslo4',
    'gracz5': 'haslo5',
    'gracz6': 'haslo6'
}

# Stan gry
game_state = {
    'deck': [],
    'players': {},
    'community_cards': [],
    'current_player': None,
    'phase': 'waiting',  # waiting, dealing, exchange, showdown
    'points': {}
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def create_deck():
    """Tworzy talię 52 kart"""
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♠', '♥', '♦', '♣']
    deck = [{'rank': r, 'suit': s} for r in ranks for s in suits]
    random.shuffle(deck)
    return deck

def evaluate_hand(cards):
    """Ocena układu pokerowego - zwraca punkty"""
    # Uproszczona ocena - w pełnej wersji trzeba by sprawdzić wszystkie ukлады
    ranks = [c['rank'] for c in cards]
    suits = [c['suit'] for c in cards]
    
    # Liczenie wartości kart
    rank_values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, 
                   '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
    
    values = sorted([rank_values[r] for r in ranks], reverse=True)
    
    # Para
    if len(set(ranks)) == 4:
        return 200 + values[0]
    # Dwie pary
    elif len(set(ranks)) == 3:
        return 400 + values[0]
    # Trzy karty
    elif len(set(ranks)) == 3 and any(ranks.count(r) == 3 for r in ranks):
        return 600 + values[0]
    # Strit
    elif len(set(values)) == 5 and max(values) - min(values) == 4:
        return 800 + values[0]
    # Kolor
    elif len(set(suits)) == 1:
        return 1000 + values[0]
    # Full
    elif len(set(ranks)) == 2 and any(ranks.count(r) == 3 for r in ranks):
        return 1200 + values[0]
    # Karetka
    elif len(set(ranks)) == 2:
        return 1400 + values[0]
    # Strit kolorystyczny
    elif len(set(suits)) == 1 and len(set(values)) == 5 and max(values) - min(values) == 4:
        return 1600 + values[0]
    # Wysoka karta
    else:
        return values[0]

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('game'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in USERS and USERS[username] == password:
            session['username'] = username
            if username not in game_state['players']:
                game_state['players'][username] = {
                    'hand': [],
                    'points': 0,  # Startowe punkty
                    'active': True
                }
            return redirect(url_for('game'))
        else:
            return render_template('login.html', error='Nieprawidlowe dane logowania')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/game')
@login_required
def game():
    return render_template('game.html', username=session['username'])

@app.route('/api/start_game', methods=['POST'])
@login_required
def start_game():
    active_players = [
        player for player, data in game_state['players'].items()
        if data.get('active', True)
    ]

    if len(active_players) < 2:
        return jsonify({
            'status': 'error',
            'message': 'Do rozpoczęcia gry muszą być zalogowani co najmniej 2 gracze.'
        }), 400

    game_state['deck'] = create_deck()
    game_state['winner'] = None

    for player in active_players:
        game_state['players'][player]['hand'] = [
            game_state['deck'].pop() for _ in range(5)
        ]

    game_state['current_player'] = active_players[0]
    game_state['phase'] = 'exchange'

    return jsonify({
        'status': 'success',
        'message': 'Gra rozpoczęta.'
    })

@app.route('/api/get_state')
@login_required
def get_state():
    username = session['username']

    players_data = {}

    for player, data in game_state['players'].items():
        players_data[player] = {
            'points': data.get('points', 1),
            'active': data.get('active', True)
        }

    return jsonify({
        'username': username,
        'hand': game_state['players'].get(username, {}).get('hand', []),
        'points': game_state['players'].get(username, {}).get('points', 1),
        'phase': game_state.get('phase', 'waiting'),
        'current_player': game_state.get('current_player'),
        'players': players_data,
        'winner': game_state.get('winner')
    })

    return jsonify(player_data)
    
@app.route('/api/exchange_cards', methods=['POST'])
@login_required
def exchange_cards():
    """Wymiana kart"""
    data = request.get_json()
    cards_to_exchange = data.get('cards', [])
    username = session['username']
    
    if game_state['phase'] != 'exchange':
        return jsonify({'status': 'error', 'message': 'Nie można wymieniać kart w tej fazie'}), 400
    
    if username != game_state['current_player']:
        return jsonify({'status': 'error', 'message': 'Nie twoja kolej'}), 400
    
    # Wymiana kart
    hand = game_state['players'][username]['hand']
    for index in sorted(cards_to_exchange, reverse=True):
        if 0 <= index < len(hand):
            hand.pop(index)
    
    # Dobierz nowe karty
    for _ in range(len(cards_to_exchange)):
        if game_state['deck']:
            hand.append(game_state['deck'].pop())
    
    # Przejdź do następnego gracza lub fazy showndown
    players_list = [p for p in game_state['players'] if game_state['players'][p]['active']]
    current_index = players_list.index(username)
    
    if current_index < len(players_list) - 1:
        game_state['current_player'] = players_list[current_index + 1]
    else:
        game_state['phase'] = 'showdown'
        # Ocena układů i przyznanie punktůw
        evaluate_and_award()
    
    return jsonify({'status': 'success'})

def evaluate_and_award():
    active_players = [
        player for player, data in game_state['players'].items()
        if data.get('active', True) and len(data.get('hand', [])) == 5
    ]

    if not active_players:
        game_state['winner'] = None
        game_state['phase'] = 'showdown'
        return

    best_player = active_players[0]
    best_score = evaluate_hand(game_state['players'][best_player]['hand'])

    for player in active_players[1:]:
        score = evaluate_hand(game_state['players'][player]['hand'])

        if score > best_score:
            best_score = score
            best_player = player

    game_state['players'][best_player]['points'] += 50
    game_state['winner'] = best_player
    game_state['phase'] = 'showdown'

@app.route('/api/next_round', methods=['POST'])
@login_required
def next_round():
    """Rozpocznij następną rundę"""
    return start_game()

@app.route('/api/stand', methods=['POST'])
@login_required
def stand():
    """Gracz pasuje (nie wymienia kart)"""
    username = session['username']
    
    if username != game_state['current_player']:
        return jsonify({'status': 'error', 'message': 'Nie twoja kolej'}), 400
    
    # Przejdź do następnego gracza
    players_list = [p for p in game_state['players'] if game_state['players'][p]['active']]
    current_index = players_list.index(username)
    
    if current_index < len(players_list) - 1:
        game_state['current_player'] = players_list[current_index + 1]
    else:
        game_state['phase'] = 'showdown'
        evaluate_and_award()
    
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
