from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import random
from functools import wraps

app = Flask(__name__)
app.secret_key = 'twoj_tajny_klucz_do_projektu'

# Maksymalnie 6 przygotowanych kont.
USERS = {
    'ms': 'haslo1',
    'kb': 'haslo2',
    'gs': 'haslo3',
    'kk': 'haslo4',
    'rp': 'haslo5',
    'xd': 'haslo6'
}

RANK_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12,
    'K': 13, 'A': 14
}

game_state = {
    'deck': [],
    'players': {},
    'current_player': None,
    'phase': 'waiting',
    'winner': None,
    'chat_messages': []
}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def create_deck():
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♠', '♥', '♦', '♣']
    deck = [{'rank': rank, 'suit': suit} for rank in ranks for suit in suits]
    random.shuffle(deck)
    return deck


def hand_details(cards):
    """Zwraca porównywalny klucz układu: wyższa krotka = silniejsza ręka."""
    values = sorted((RANK_VALUES[card['rank']] for card in cards), reverse=True)
    suits = [card['suit'] for card in cards]
    counts_by_value = {}

    for value in values:
        counts_by_value[value] = counts_by_value.get(value, 0) + 1

    groups = sorted(
        ((count, value) for value, count in counts_by_value.items()),
        reverse=True
    )

    is_flush = len(set(suits)) == 1
    unique_values = sorted(set(values))
    is_wheel = unique_values == [2, 3, 4, 5, 14]
    is_straight = (
        len(unique_values) == 5 and
        (unique_values[-1] - unique_values[0] == 4 or is_wheel)
    )
    straight_high = 5 if is_wheel else max(values)

    if is_straight and is_flush:
        return (8, straight_high), 'Poker królewski' if straight_high == 14 else 'Strit w kolorze'
    if groups[0][0] == 4:
        four = groups[0][1]
        kicker = groups[1][1]
        return (7, four, kicker), 'Kareta'
    if groups[0][0] == 3 and groups[1][0] == 2:
        return (6, groups[0][1], groups[1][1]), 'Full'
    if is_flush:
        return (5, *values), 'Kolor'
    if is_straight:
        return (4, straight_high), 'Strit'
    if groups[0][0] == 3:
        three = groups[0][1]
        kickers = sorted((value for value in values if value != three), reverse=True)
        return (3, three, *kickers), 'Trójka'
    if groups[0][0] == 2 and groups[1][0] == 2:
        pairs = sorted((groups[0][1], groups[1][1]), reverse=True)
        kicker = groups[2][1]
        return (2, pairs[0], pairs[1], kicker), 'Dwie pary'
    if groups[0][0] == 2:
        pair = groups[0][1]
        kickers = sorted((value for value in values if value != pair), reverse=True)
        return (1, pair, *kickers), 'Para'

    return (0, *values), 'Wysoka karta'


def evaluate_hand(cards):
    """Zachowane dla zgodności; pełne porównanie wykonuje hand_details()."""
    score, _ = hand_details(cards)
    return score


def hand_name(cards):
    _, name = hand_details(cards)
    return name


def active_players():
    return [
        player for player, data in game_state['players'].items()
        if data.get('active', True)
    ]


def advance_turn(username):
    players = active_players()
    current_index = players.index(username)

    if current_index < len(players) - 1:
        game_state['current_player'] = players[current_index + 1]
    else:
        evaluate_and_award()

def points_for_hand(cards):
    score, _ = hand_details(cards)
    hand_rank = score[0]

    # 4 = strit, 6 = full, 7 = kareta, 8 = strit w kolorze
    points_by_rank = {
        4: 2,
        6: 3,
        7: 4,
        8: 10
    }

    return points_by_rank.get(hand_rank, 1)

def evaluate_and_award():
    players = [
        player for player in active_players()
        if len(game_state['players'][player].get('hand', [])) == 5
    ]

    if not players:
        game_state['winner'] = None
        game_state['winner_points'] = 0
        game_state['winner_hand_name'] = ''
        game_state['phase'] = 'showdown'
        return

    winner = players[0]
    best_score, best_hand_name = hand_details(
        game_state['players'][winner]['hand']
    )

    for player in players[1:]:
        score, hand_name_value = hand_details(
            game_state['players'][player]['hand']
        )

        if score > best_score:
            winner = player
            best_score = score
            best_hand_name = hand_name_value

    won_points = points_for_hand(game_state['players'][winner]['hand'])

    game_state['players'][winner]['points'] += won_points
    game_state['winner'] = winner
    game_state['winner_points'] = won_points
    game_state['winner_hand_name'] = best_hand_name
    game_state['current_player'] = None
    game_state['phase'] = 'showdown'


@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('game'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if username in USERS and USERS[username] == password:
            session['username'] = username

            if username not in game_state['players']:
                game_state['players'][username] = {
                    'hand': [],
                    'points': 0,
                    'active': True
                }
            else:
                game_state['players'][username]['active'] = True

            return redirect(url_for('game'))

        return render_template('login.html', error='Nieprawidłowe dane logowania.')

    return render_template('login.html')


@app.route('/logout')
def logout():
    username = session.get('username')
    if username in game_state['players']:
        game_state['players'][username]['active'] = False
    session.clear()
    return redirect(url_for('login'))


@app.route('/game')
@login_required
def game():
    return render_template('game.html', username=session['username'])

@app.route('/api/chat', methods=['GET'])
@login_required
def get_chat():
    return jsonify({
        'messages': game_state.get('chat_messages', [])
    })


@app.route('/api/chat', methods=['POST'])
@login_required
def send_chat_message():
    data = request.get_json(silent=True) or {}
    text = str(data.get('text', '')).strip()

    if not text:
        return jsonify({
            'status': 'error',
            'message': 'Wiadomość nie może być pusta.'
        }), 400

    if len(text) > 180:
        return jsonify({
            'status': 'error',
            'message': 'Wiadomość może mieć maksymalnie 180 znaków.'
        }), 400

    game_state['chat_messages'].append({
        'user': session['username'],
        'text': text
    })

    # Zostawiamy tylko 50 ostatnich wiadomości.
    game_state['chat_messages'] = game_state['chat_messages'][-50:]

    return jsonify({'status': 'success'})

@app.route('/api/start_game', methods=['POST'])
@login_required
def start_game():
    players = active_players()

    if len(players) < 2:
        return jsonify({
            'status': 'error',
            'message': 'Do rozpoczęcia gry muszą być zalogowani co najmniej 2 gracze.'
        }), 400

    game_state['deck'] = create_deck()
    game_state['winner'] = None
    game_state['winner_points'] = 0
    game_state['winner_hand_name'] = ''
    game_state['phase'] = 'dealing'

    for player in players:
        game_state['players'][player]['hand'] = [
            game_state['deck'].pop() for _ in range(5)
        ]

    game_state['current_player'] = players[0]
    game_state['phase'] = 'exchange'

    return jsonify({
        'status': 'success',
        'message': 'Gra rozpoczęta. Rozdano karty z jednej wspólnej talii.'
    })


@app.route('/api/get_state')
@login_required
def get_state():
    username = session['username']
    players_data = {}
    showdown = game_state.get('phase') == 'showdown'

    for player, data in game_state['players'].items():
        player_info = {
            'points': data.get('points', 0),
            'active': data.get('active', True)
        }

        # Cudze karty pokazujemy wyłącznie po zakończeniu rundy.
        if showdown:
            hand = data.get('hand', [])
            player_info['hand'] = hand
            player_info['hand_name'] = hand_name(hand) if len(hand) == 5 else ''

        players_data[player] = player_info

    return jsonify({
        'username': username,
        'hand': game_state['players'].get(username, {}).get('hand', []),
        'points': game_state['players'].get(username, {}).get('points', 0),
        'phase': game_state.get('phase', 'waiting'),
        'current_player': game_state.get('current_player'),
        'players': players_data,
        'winner': game_state.get('winner'),
        'winner_points': game_state.get('winner_points', 0),
        'winner_hand_name': game_state.get('winner_hand_name', '')
    })


@app.route('/api/exchange_cards', methods=['POST'])
@login_required
def exchange_cards():
    data = request.get_json(silent=True) or {}
    cards_to_exchange = data.get('cards', [])
    username = session['username']

    if game_state.get('phase') != 'exchange':
        return jsonify({'status': 'error', 'message': 'Nie można wymieniać kart w tej fazie.'}), 400

    if username != game_state.get('current_player'):
        return jsonify({'status': 'error', 'message': 'Nie Twoja kolej.'}), 400

    if not isinstance(cards_to_exchange, list):
        return jsonify({'status': 'error', 'message': 'Nieprawidłowa lista kart.'}), 400

    if len(cards_to_exchange) > 5 or len(set(cards_to_exchange)) != len(cards_to_exchange):
        return jsonify({'status': 'error', 'message': 'Możesz wymienić od 0 do 5 różnych kart.'}), 400

    if not all(isinstance(index, int) and 0 <= index < 5 for index in cards_to_exchange):
        return jsonify({'status': 'error', 'message': 'Wybrano nieprawidłową kartę.'}), 400

    hand = game_state['players'][username]['hand']

    for index in sorted(cards_to_exchange, reverse=True):
        hand.pop(index)

    for _ in cards_to_exchange:
        if not game_state['deck']:
            return jsonify({'status': 'error', 'message': 'W talii zabrakło kart.'}), 400
        hand.append(game_state['deck'].pop())

    advance_turn(username)
    return jsonify({'status': 'success'})


@app.route('/api/stand', methods=['POST'])
@login_required
def stand():
    username = session['username']

    if game_state.get('phase') != 'exchange':
        return jsonify({'status': 'error', 'message': 'Nie można zakończyć tury w tej fazie.'}), 400

    if username != game_state.get('current_player'):
        return jsonify({'status': 'error', 'message': 'Nie Twoja kolej.'}), 400

    advance_turn(username)
    return jsonify({'status': 'success'})

@app.route('/api/reset_points', methods=['POST'])
@login_required
def reset_points():
    if session.get('username') != 'ms':
        return jsonify({
            'status': 'error',
            'message': 'Tylko użytkownik ms może resetować punkty.'
        }), 403

    # Nie zmieniaj punktów w trakcie wymiany kart — najpierw trzeba zakończyć rundę.
    if game_state.get('phase') == 'exchange':
        return jsonify({
            'status': 'error',
            'message': 'Nie można resetować punktów w trakcie rundy. Zakończ ją lub poczekaj na pokaz kart.'
        }), 400

    for player_data in game_state['players'].values():
        player_data['points'] = 0
        player_data['hand'] = []

    game_state['deck'] = []
    game_state['winner'] = None
    game_state['current_player'] = None
    game_state['phase'] = 'waiting'

    return jsonify({
        'status': 'success',
        'message': 'Wszystkie punkty zostały wyzerowane. Można rozpocząć nową grę.'
    })

@app.route('/api/next_round', methods=['POST'])
@login_required
def next_round():
    return start_game()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
