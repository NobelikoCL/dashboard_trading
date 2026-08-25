from collections import OrderedDict
from datetime import timedelta, timezone as dt_timezone
from decimal import Decimal
import math

from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json


def number(value):
    return float(value or 0)


def ensure_baselines_table(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS account_baselines (
        account_login BIGINT PRIMARY KEY,
        initial_balance NUMERIC NOT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ok', 'database': 'connected'})
    except Exception as error:
        return JsonResponse({'status': 'degraded', 'database': 'unavailable', 'detail': str(error)}, status=503)


@require_GET
def dashboard(request):
    period = request.GET.get('period', '30D').upper()
    days = {'1D': 1, '7D': 7, '30D': 30, '90D': 90, 'YTD': 365}.get(period, 30)
    since = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    try:
        with connection.cursor() as cursor:
            ensure_baselines_table(cursor)
            cursor.execute('''
                SELECT account_login, server, broker, account_name, balance, equity,
                       open_positions, captured_at, terminal_name
                FROM account_snapshots WHERE captured_at >= %s
                ORDER BY captured_at ASC
            ''', [since])
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            cursor.execute('SELECT account_login, initial_balance FROM account_baselines')
            baselines = {row[0]: number(row[1]) for row in cursor.fetchall()}
    except Exception as error:
        return JsonResponse({'error': 'No se pudo consultar account_snapshots', 'detail': str(error)}, status=503)

    if not rows:
        return JsonResponse({'summary': empty_summary(), 'curve': [], 'curve_labels': [], 'account_curves': [], 'alerts': [{'level': 'critical', 'title': 'Sin datos', 'detail': 'No existen snapshots en el periodo seleccionado'}], 'accounts': [], 'period': period})

    by_account = OrderedDict()
    for row in rows:
        by_account[row['account_login']] = row
    equities = [number(row['equity']) for row in rows]
    current_equity = sum(number(row['equity']) for row in by_account.values())
    latest_capture = rows[-1]['captured_at']
    if latest_capture.tzinfo is None:
        latest_capture = latest_capture.replace(tzinfo=dt_timezone.utc)
    snapshot_age = max(0, int((timezone.now() - latest_capture).total_seconds()))
    initial_by_account = OrderedDict()
    for row in rows:
        initial_by_account.setdefault(row['account_login'], number(row['equity']))
    initial_equity = sum(initial_by_account.values()) or current_equity
    baseline_total = sum(baselines.get(key, initial_by_account.get(key, 0)) for key in by_account)
    cumulative_profit = current_equity - baseline_total
    curve, curve_labels = portfolio_curve(rows, days)
    account_curves = account_curve_data(rows, days)
    portfolio_values = curve or [current_equity]
    peak = max(portfolio_values) or current_equity
    trough = min(portfolio_values) or current_equity
    absolute_dd = max(0, (peak - current_equity) / peak * 100) if peak else 0
    max_dd = max(0, (peak - trough) / peak * 100) if peak else 0
    returns = []
    for key in by_account:
        account_rows = [row for row in rows if row['account_login'] == key]
        returns.extend((number(account_rows[i]['equity']) / number(account_rows[i - 1]['equity']) - 1)
                       for i in range(1, len(account_rows)) if number(account_rows[i - 1]['equity']))
    gains = sum(x for x in returns if x > 0)
    losses = abs(sum(x for x in returns if x < 0))
    win_rate = (len([x for x in returns if x > 0]) / len(returns) * 100) if returns else 0
    average = sum(returns) / len(returns) if returns else 0
    deviation = math.sqrt(sum((x - average) ** 2 for x in returns) / len(returns)) if returns else 0
    accounts = []
    alerts = []
    for key, row in by_account.items():
        account_equities = [number(x['equity']) for x in rows if x['account_login'] == key]
        account_peak = max(account_equities) or number(row['equity'])
        account_dd = max(0, (account_peak - number(row['equity'])) / account_peak * 100) if account_peak else 0
        account_initial = baselines.get(key, account_equities[0] if account_equities else number(row['equity']))
        account_profit = number(row['equity']) - account_initial
        stale = snapshot_age > 120
        if stale:
            alerts.append({'level': 'critical', 'title': 'Datos desactualizados', 'detail': f"{row['terminal_name'] or key} no actualiza desde hace {snapshot_age // 60} min"})
        if account_dd > 8:
            alerts.append({'level': 'warning', 'title': 'Drawdown elevado', 'detail': f"{row['terminal_name'] or key} alcanza {account_dd:.2f}%"})
        accounts.append({'account_login': key, 'name': row['account_name'] or f"Account {row['account_login']}",
                         'login': f"... {str(row['account_login'])[-4:]}",
                         'strategy': row['terminal_name'] or 'Estrategia no definida',
                         'broker': row['broker'] or row['server'], 'equity': number(row['equity']), 'initial_balance': account_initial,
                         'balance': number(row['balance']), 'profit_loss': account_profit,
                         'return_percent': (account_profit / account_initial * 100) if account_initial else 0,
                         'day': 0, 'dd': account_dd, 'dd_amount': max(0, account_peak - number(row['equity'])),
                         'exposure': None, 'stale': stale, 'status': 'stale' if stale else ('watch' if account_dd > 8 else 'healthy'),
                         'positions': row['open_positions']})
    for account in accounts:
        account_rows = [x for x in rows if f"... {str(x['account_login'])[-4:]}" == account['login']]
        if len(account_rows) > 1 and number(account_rows[-2]['equity']):
            account['day'] = (number(account_rows[-1]['equity']) / number(account_rows[-2]['equity']) - 1) * 100
    equity_change = (current_equity / initial_equity - 1) * 100
    cumulative_percent = (cumulative_profit / baseline_total * 100) if baseline_total else 0
    return JsonResponse({'summary': {'equity': round(current_equity, 2), 'balance': round(sum(number(row['balance']) for row in by_account.values()), 2), 'initial_balance_total': round(baseline_total, 2), 'equity_change': round(equity_change, 2), 'cumulative_profit': round(cumulative_profit, 2), 'cumulative_percent': round(cumulative_percent, 2), 'profit_percent': round(max(equity_change, 0), 2), 'loss_percent': round(min(equity_change, 0), 2), 'absolute_drawdown': round(absolute_dd, 2), 'max_drawdown': round(max_dd, 2), 'win_rate': round(win_rate, 2), 'profit_factor': round(gains / losses if losses else 0, 2), 'open_positions': sum(x['open_positions'] for x in by_account.values()), 'accounts': len(by_account), 'sharpe': round((average / deviation * math.sqrt(252)) if deviation else 0, 2), 'exposure_available': False, 'latest_capture': rows[-1]['captured_at'].isoformat(), 'snapshot_age_seconds': snapshot_age, 'data_status': 'stale' if snapshot_age > 120 else 'live'}, 'curve': curve, 'curve_labels': curve_labels, 'account_curves': account_curves, 'alerts': alerts, 'accounts': accounts, 'period': period})


def portfolio_curve(rows, days):
    latest = OrderedDict()
    for row in rows:
        captured = row['captured_at']
        if days == 1:
            bucket = captured.replace(second=0, microsecond=0)
        elif days == 7:
            bucket = captured.replace(minute=0, second=0, microsecond=0)
        elif days == 30:
            bucket = captured.replace(hour=(captured.hour // 4) * 4, minute=0, second=0, microsecond=0)
        else:
            bucket = captured.date().isoformat()
        latest.setdefault(bucket, {})[row['account_login']] = number(row['equity'])
    limit = 1440 if days == 1 else 168 if days == 7 else 100 if days == 30 else 365
    items = [(bucket, sum(accounts.values())) for bucket, accounts in latest.items()][-limit:]
    return [value for _, value in items], [bucket.isoformat() if hasattr(bucket, 'isoformat') else str(bucket) for bucket, _ in items]


def account_curve_data(rows, days):
    buckets = OrderedDict()
    for row in rows:
        captured = row['captured_at']
        if days == 1:
            bucket = captured.replace(second=0, microsecond=0)
        elif days == 7:
            bucket = captured.replace(minute=0, second=0, microsecond=0)
        elif days == 30:
            bucket = captured.replace(hour=(captured.hour // 4) * 4, minute=0, second=0, microsecond=0)
        else:
            bucket = captured.date().isoformat()
        buckets.setdefault(bucket, {})[row['account_login']] = number(row['equity'])
    logins = OrderedDict((row['account_login'], row['terminal_name'] or f"Cuenta {row['account_login']}") for row in rows)
    return [{'name': name, 'values': [bucket.get(login, None) for bucket in buckets.values()]} for login, name in logins.items()]


def empty_summary():
    return {'equity': 0, 'balance': 0, 'initial_balance_total': 0, 'equity_change': 0, 'cumulative_profit': 0, 'cumulative_percent': 0, 'profit_percent': 0, 'loss_percent': 0, 'absolute_drawdown': 0, 'max_drawdown': 0, 'win_rate': 0, 'profit_factor': 0, 'open_positions': 0, 'accounts': 0, 'sharpe': 0, 'exposure_available': False, 'latest_capture': None}


@csrf_exempt
@require_http_methods(['POST'])
def save_baseline(request):
    try:
        payload = json.loads(request.body)
        login = int(payload['account_login'])
        initial_balance = float(payload['initial_balance'])
        if initial_balance < 0:
            raise ValueError('El saldo inicial no puede ser negativo')
        with connection.cursor() as cursor:
            ensure_baselines_table(cursor)
            cursor.execute('''INSERT INTO account_baselines (account_login, initial_balance, updated_at)
                              VALUES (%s, %s, CURRENT_TIMESTAMP)
                              ON CONFLICT (account_login) DO UPDATE SET initial_balance = EXCLUDED.initial_balance,
                              updated_at = CURRENT_TIMESTAMP''', [login, initial_balance])
        return JsonResponse({'status': 'saved', 'account_login': login, 'initial_balance': initial_balance})
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        return JsonResponse({'error': str(error)}, status=400)
