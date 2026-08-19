"""
Root-cause regression tests for two reported KUMUSH Store defects:

PROBLEM 1 (product image not appearing): exhaustive tracing (model ->
serializer -> view -> parser -> MEDIA storage -> template -> browser) and
live end-to-end testing (in-process API client, real dev server + curl,
and a real headless-browser session) found the entire pipeline already
correct. These tests pin that down as a regression net rather than "fix"
anything that isn't broken.

PROBLEM 2 (stock=N showing as N duplicate cards): proven to actually be
caused by a missing double-submit guard on the admin "Saqlash" button in
templates/erp/store_manage.html (doSaveItem()), not by `stock` being
interpreted as an object count anywhere in the backend. StoreItem.stock is,
and always was, a single inventory-count field — confirmed here by asserting
that a single create call with any stock value produces exactly one row.
The double-submit fix itself is pure frontend JS (a `saveBtn.disabled`
guard) and was verified with a real Playwright browser session, not here —
there is no JS test runner in this stack (consistent with how prior
frontend-only fixes in this project were verified).
"""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.store.models import StoreItem
from apps.students.models import Student


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        phone='+998900000096', password='pass1234',
        full_name='Admin User', role=User.Role.ADMIN,
    )


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        phone='+998900000097', password='pass1234',
        full_name='Student User', role=User.Role.STUDENT,
    )
    Student.objects.create(user=user, phone=user.phone, coins=1000)
    return user


def make_png(name='pen.png', size=(10, 10), color=(255, 0, 0)):
    buf = io.BytesIO()
    Image.new('RGB', size, color=color).save(buf, format='PNG')
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='image/png')


@pytest.mark.django_db
class TestStockIsInventoryCountNotObjectCount:
    """StoreItem.stock must always mean 'how many are available', never
    'how many rows to create'. One POST call == one row, regardless of
    the stock value submitted."""

    @pytest.mark.parametrize('stock_value', [0, 1, 2, 10])
    def test_single_create_call_produces_exactly_one_row(self, admin_user, stock_value):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/items/', {
            'name': f'StockTest{stock_value}', 'price': 500, 'stock': stock_value,
        }, format='json')
        assert resp.status_code == 201
        assert StoreItem.objects.filter(name=f'StockTest{stock_value}').count() == 1
        item = StoreItem.objects.get(name=f'StockTest{stock_value}')
        assert item.stock == stock_value

    def test_stock_ten_is_stored_as_a_single_integer_field(self, admin_user):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/items/', {'name': 'TenPens', 'price': 100, 'stock': 10}, format='json')
        assert resp.status_code == 201
        assert resp.data['stock'] == 10
        # exactly one row in the DB, not ten
        assert StoreItem.objects.filter(name='TenPens').count() == 1

    def test_list_endpoint_returns_one_entry_per_created_item(self, admin_user):
        client = auth_client(admin_user)
        client.post('/api/v1/store/items/', {'name': 'ListCheck', 'price': 100, 'stock': 7}, format='json')
        resp = client.get('/api/v1/store/items/?search=ListCheck')
        rows = resp.data.get('results', resp.data)
        assert len(rows) == 1
        assert rows[0]['stock'] == 7

    def test_two_independent_create_calls_are_two_legitimate_rows(self, admin_user):
        """
        This is NOT the bug — it's the correct, intentional backend contract:
        the API has no reason to reject two distinct create requests for the
        same name (a restock under a new listing, a deliberate duplicate
        product, etc. are legitimate business cases). The actual defect
        (missing debounce on the admin Save button, causing an ACCIDENTAL
        double-submit) is a frontend concern, fixed in store_manage.html and
        verified via a real browser session — not something this backend
        test asserts against, since correctly rejecting all repeat calls
        would also block legitimate restocking via two deliberate submissions.
        """
        client = auth_client(admin_user)
        r1 = client.post('/api/v1/store/items/', {'name': 'TwoCalls', 'price': 500, 'stock': 2}, format='json')
        r2 = client.post('/api/v1/store/items/', {'name': 'TwoCalls', 'price': 500, 'stock': 2}, format='json')
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert StoreItem.objects.filter(name='TwoCalls').count() == 2


@pytest.mark.django_db
class TestProductImageLifecycle:
    """Traces the full image pipeline: multipart upload -> request.FILES ->
    ImageField -> MEDIA storage -> serialized URL -> what the JS templates
    actually read (`it.image`)."""

    def test_product_can_be_created_with_image(self, admin_user):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/items/', {
            'name': 'ImagedItem', 'price': 500, 'stock': 2, 'image': make_png(),
        }, format='multipart')
        assert resp.status_code == 201

    def test_image_field_is_populated_and_saved(self, admin_user):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/items/', {
            'name': 'ImagedItem2', 'price': 500, 'stock': 2, 'image': make_png(),
        }, format='multipart')
        item = StoreItem.objects.get(pk=resp.data['id'])
        assert item.image
        assert item.image.name.startswith('store/items/')
        assert item.image.storage.exists(item.image.name)

    def test_image_url_is_generated_correctly(self, admin_user):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/items/', {
            'name': 'ImagedItem3', 'price': 500, 'stock': 2, 'image': make_png(),
        }, format='multipart')
        # This is exactly the value templates/erp/store.html and store_manage.html
        # bind to `<img src="${it.image}">` — must be a usable, absolute URL.
        assert resp.data['image'].startswith('http')
        assert '/media/store/items/' in resp.data['image']

    def test_list_and_retrieve_return_the_same_working_url(self, admin_user):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/items/', {
            'name': 'ImagedItem4', 'price': 500, 'stock': 2, 'image': make_png(),
        }, format='multipart')
        detail = client.get(f"/api/v1/store/items/{resp.data['id']}/")
        listing = client.get('/api/v1/store/items/?search=ImagedItem4')
        row = listing.data.get('results', listing.data)[0]
        assert detail.data['image'] == resp.data['image']
        assert row['image'] == resp.data['image']

    def test_edit_without_touching_image_preserves_it(self, admin_user):
        """Regression for the plausible real-world path: an admin edits an
        existing item (e.g. changes the price) without re-selecting a file —
        PATCH must not clear the existing image."""
        client = auth_client(admin_user)
        created = client.post('/api/v1/store/items/', {
            'name': 'EditPreserve', 'price': 500, 'stock': 2, 'image': make_png(),
        }, format='multipart')
        original_image = created.data['image']

        patched = client.patch(f"/api/v1/store/items/{created.data['id']}/",
                                {'price': 999}, format='json')
        assert patched.status_code == 200
        assert patched.data['image'] == original_image

    def test_explicit_image_removal_clears_it(self, admin_user):
        client = auth_client(admin_user)
        created = client.post('/api/v1/store/items/', {
            'name': 'RemoveImg', 'price': 500, 'stock': 2, 'image': make_png(),
        }, format='multipart')
        patched = client.patch(f"/api/v1/store/items/{created.data['id']}/",
                                {'image': None}, format='json')
        assert patched.status_code == 200
        assert patched.data['image'] is None

    def test_product_without_image_serializes_safely(self, admin_user):
        client = auth_client(admin_user)
        resp = client.post('/api/v1/store/items/', {'name': 'NoImage', 'price': 500, 'stock': 1}, format='json')
        assert resp.status_code == 201
        assert resp.data['image'] is None

        listing = client.get('/api/v1/store/items/?search=NoImage')
        row = listing.data.get('results', listing.data)[0]
        assert row['image'] is None


@pytest.mark.django_db
class TestPurchaseDoesNotAffectItemRowCount:
    """Buying a unit must change `stock`, never the number of StoreItem rows
    or trigger any card duplication/removal."""

    def test_buying_one_unit_decrements_stock_without_changing_row_count(self, admin_user, student_user):
        client_admin = auth_client(admin_user)
        item_resp = client_admin.post('/api/v1/store/items/', {
            'name': 'BuyableItem', 'price': 100, 'stock': 2,
        }, format='json')
        item_id = item_resp.data['id']

        client_student = auth_client(student_user)
        pr_resp = client_student.post('/api/v1/store/requests/', {'item': item_id}, format='json')
        assert pr_resp.status_code == 201

        approve_resp = client_admin.post(f"/api/v1/store/requests/{pr_resp.data['id']}/approve/")
        assert approve_resp.status_code == 200

        assert StoreItem.objects.filter(name='BuyableItem').count() == 1  # still exactly one row
        item = StoreItem.objects.get(pk=item_id)
        assert item.stock == 1  # decremented, not the row count

        listing = client_admin.get('/api/v1/store/items/?search=BuyableItem')
        assert len(listing.data.get('results', listing.data)) == 1
