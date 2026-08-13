"""
Tests for Student.apply_kumush_and_xp() — the single shared atomic
primitive every KUMUSH-earning/spending path routes through.
"""
import pytest

from apps.accounts.models import User
from apps.store.models import KumushTransaction
from apps.students.models import Student


@pytest.mark.django_db
def test_apply_kumush_and_xp_earns_with_ledger():
    user = User.objects.create_user(phone='+998900009001', password='x', full_name='T', role='student')
    s = Student.objects.create(user=user, phone=user.phone, coins=50, xp_points=100)

    txn = s.apply_kumush_and_xp(xp_delta=10, coins_delta=30, reason='test earn',
                                 source_type='unit_test', source_id='abc')
    s.refresh_from_db()
    assert s.coins == 80
    assert s.xp_points == 110
    assert txn.amount == 30
    assert txn.type == KumushTransaction.Type.EARN
    assert txn.balance_before == 50
    assert txn.balance_after == 80
    assert txn.source_type == 'unit_test'
    assert txn.source_id == 'abc'


@pytest.mark.django_db
def test_apply_kumush_and_xp_refuses_negative_balance():
    user = User.objects.create_user(phone='+998900009002', password='x', full_name='T2', role='student')
    s = Student.objects.create(user=user, phone=user.phone, coins=10)

    txn = s.apply_kumush_and_xp(coins_delta=-50, reason='too much')
    s.refresh_from_db()
    assert txn is None
    assert s.coins == 10  # unchanged
    assert KumushTransaction.objects.filter(student=s).count() == 0


@pytest.mark.django_db
def test_apply_kumush_and_xp_negative_spend_creates_spend_type():
    user = User.objects.create_user(phone='+998900009005', password='x', full_name='T5', role='student')
    s = Student.objects.create(user=user, phone=user.phone, coins=100)

    txn = s.apply_kumush_and_xp(coins_delta=-30, reason='manual debit')
    assert txn.type == KumushTransaction.Type.SPEND
    assert txn.amount == -30
    assert txn.balance_before == 100
    assert txn.balance_after == 70


@pytest.mark.django_db
def test_pure_xp_delta_writes_no_ledger_row():
    user = User.objects.create_user(phone='+998900009006', password='x', full_name='T6', role='student')
    s = Student.objects.create(user=user, phone=user.phone, coins=0, xp_points=0)

    txn = s.apply_kumush_and_xp(xp_delta=20, coins_delta=0, reason='xp only')
    s.refresh_from_db()
    assert txn is None
    assert s.xp_points == 20
    assert KumushTransaction.objects.filter(student=s).count() == 0


@pytest.mark.django_db
def test_add_xp_backward_compatible_and_ledger_backed():
    user = User.objects.create_user(phone='+998900009003', password='x', full_name='T3', role='student')
    s = Student.objects.create(user=user, phone=user.phone, coins=0, xp_points=0)

    s.add_xp(25, reason='ZUKKO Challenge')
    s.refresh_from_db()
    assert s.coins == 25
    assert s.xp_points == 25
    assert KumushTransaction.objects.filter(student=s, reason='ZUKKO Challenge').exists()


@pytest.mark.django_db
def test_add_xp_only_does_not_touch_coins_or_ledger():
    user = User.objects.create_user(phone='+998900009004', password='x', full_name='T4', role='student')
    s = Student.objects.create(user=user, phone=user.phone, coins=5, xp_points=0)

    s.add_xp_only(40)
    s.refresh_from_db()
    assert s.xp_points == 40
    assert s.coins == 5  # untouched
    assert KumushTransaction.objects.filter(student=s).count() == 0


@pytest.mark.django_db
def test_level_recomputed_correctly():
    user = User.objects.create_user(phone='+998900009007', password='x', full_name='T7', role='student')
    s = Student.objects.create(user=user, phone=user.phone, xp_points=490)

    s.apply_kumush_and_xp(xp_delta=20, coins_delta=0, reason='level up')
    s.refresh_from_db()
    assert s.xp_points == 510
    assert s.level == 2  # 510 // 500 + 1
