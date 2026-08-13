from django.db import IntegrityError, transaction
from django.db.models import Count, F, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import ActivityLog
from apps.notifications.views import log_activity
from apps.students.models import Student

from .models import KumushTransaction, PurchaseRequest, StoreItem
from .permissions import (
    IsStoreManager,
    IsStudentOrStoreManager,
    StoreItemPermission,
)
from .serializers import (
    KumushTransactionSerializer,
    ManualKumushAdjustmentSerializer,
    PurchaseRequestSerializer,
    StoreItemSerializer,
)


class DuplicatePendingRequest(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Bu buyum uchun sizda allaqachon kutilayotgan so'rov bor."
    default_code = 'duplicate_pending_request'


class StoreItemViewSet(viewsets.ModelViewSet):
    """
    /api/v1/store/items/ — Do'kon buyumlari.
    O'qish: Student/Teacher/Admin/Developer. Yozish: faqat Admin/Developer.
    O'chirish yo'q — faqat is_active bilan faollashtirish/o'chirish (soft).
    """
    serializer_class    = StoreItemSerializer
    permission_classes  = [StoreItemPermission]
    http_method_names   = ['get', 'post', 'put', 'patch', 'head', 'options']
    filter_backends     = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields    = ['is_active']
    search_fields        = ['name', 'description']
    ordering             = ['-created_at']

    def get_queryset(self):
        qs = StoreItem.objects.select_related('created_by')
        u = self.request.user
        if u.is_admin or u.is_developer:
            return qs
        return qs.filter(is_active=True)

    def perform_create(self, serializer):
        item = serializer.save(created_by=self.request.user)
        log_activity(self.request.user, ActivityLog.Action.CREATE, 'StoreItem', item.pk, str(item),
                     request=self.request)

    def perform_update(self, serializer):
        old = serializer.instance
        old_vals = {'name': old.name, 'price': old.price, 'stock': old.stock, 'is_active': old.is_active}
        item = serializer.save()
        new_vals = {'name': item.name, 'price': item.price, 'stock': item.stock, 'is_active': item.is_active}
        changes = {k: {'old': old_vals[k], 'new': v} for k, v in new_vals.items() if old_vals[k] != v}
        log_activity(self.request.user, ActivityLog.Action.UPDATE, 'StoreItem', item.pk, str(item),
                     changes=changes or None, request=self.request)


class PurchaseRequestViewSet(viewsets.ModelViewSet):
    """
    /api/v1/store/requests/ — Xarid so'rovlari.
    Student — o'z so'rovlarini yaratadi/ko'radi. Admin/Developer — hammasini ko'radi,
    tasdiqlaydi/rad etadi (generic PUT/PATCH/DELETE yo'q — faqat approve/reject action).
    """
    serializer_class    = PurchaseRequestSerializer
    permission_classes  = [IsStudentOrStoreManager]
    http_method_names   = ['get', 'post', 'head', 'options']
    filter_backends     = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields    = ['status', 'student']
    ordering             = ['-requested_at']

    def get_queryset(self):
        qs = PurchaseRequest.objects.select_related('student__user', 'item', 'decided_by')
        u = self.request.user
        if u.is_admin or u.is_developer:
            return qs
        student = getattr(u, 'student_profile', None)
        return qs.filter(student=student) if student else qs.none()

    def perform_create(self, serializer):
        student = getattr(self.request.user, 'student_profile', None)
        if not student:
            raise PermissionDenied("Faqat o'quvchilar xarid so'rovi yubora oladi.")
        item = serializer.validated_data.get('item')
        if item is None:
            raise ValidationError({'item': 'Buyum tanlanmagan.'})
        if not item.is_active:
            raise ValidationError({'detail': 'Bu buyum hozircha faol emas.'})
        if item.stock <= 0:
            raise ValidationError({'detail': 'HOZIRCHA MAVJUD EMAS'})
        if student.coins < item.price:
            raise ValidationError({'detail': 'Kumushingiz yetarli emas.'})
        try:
            # Nested atomic (savepoint): a bare IntegrityError caught while
            # inside an outer atomic block (e.g. ATOMIC_REQUESTS, or the
            # transactional test wrapper) would otherwise poison that whole
            # transaction. The savepoint contains the failure to just this
            # insert.
            with transaction.atomic():
                pr = serializer.save(student=student, price_at_request=item.price)
        except IntegrityError:
            # Lost a race against unique_pending_request_per_student_item —
            # another PENDING request for this (student, item) already
            # exists (created concurrently, e.g. duplicate/double-click
            # submission). Clean 409 instead of a raw 500.
            raise DuplicatePendingRequest()
        log_activity(self.request.user, ActivityLog.Action.CREATE, 'PurchaseRequest', pr.pk, str(pr),
                     request=self.request)

    @action(detail=True, methods=['post'], permission_classes=[IsStoreManager])
    def approve(self, request, pk=None):
        with transaction.atomic():
            try:
                pr = PurchaseRequest.objects.select_for_update().get(pk=pk)
            except PurchaseRequest.DoesNotExist:
                return Response({'detail': "So'rov topilmadi."}, status=status.HTTP_404_NOT_FOUND)
            if pr.status != PurchaseRequest.Status.PENDING:
                return Response({'detail': "Bu so'rov allaqachon hal qilingan."},
                                 status=status.HTTP_400_BAD_REQUEST)

            item = StoreItem.objects.select_for_update().get(pk=pr.item_id)
            student = Student.objects.select_for_update().get(pk=pr.student_id)
            # So'rov paytida qulflangan narx ishlatiladi — item.price shu orada
            # o'zgargan bo'lishi mumkin, lekin o'quvchi ko'rgan/rozi bo'lgan narx
            # price_at_request bo'lib qoladi.
            price = pr.price_at_request

            if item.stock <= 0:
                return Response({'detail': "Buyum tugagan (qoldiq yo'q)."}, status=status.HTTP_400_BAD_REQUEST)
            if student.coins < price:
                return Response({'detail': "O'quvchining Kumushi yetarli emas."},
                                 status=status.HTTP_400_BAD_REQUEST)

            # Routed through the shared ledger primitive (not spend_coins() +
            # a hand-built KumushTransaction) so the SPEND row carries full
            # forensic metadata — created_by/balance_before/balance_after/
            # source_type/source_id — the same guarantee every other KUMUSH
            # mutation in the system now has. student is already locked
            # above; apply_kumush_and_xp() re-locks the same row (harmless,
            # same transaction) and refuses (returns None, no mutation) if
            # the balance can't cover it — defensive belt-and-braces behind
            # the explicit check just above, which already guards this.
            txn = student.apply_kumush_and_xp(
                coins_delta=-price, reason=f"{item.name} sotib olindi", created_by=request.user,
                source_type='store_purchase', source_id=str(pr.pk),
            )
            if txn is None:
                return Response({'detail': "O'quvchining Kumushi yetarli emas."},
                                 status=status.HTTP_400_BAD_REQUEST)
            KumushTransaction.objects.filter(pk=txn.pk).update(purchase=pr)
            StoreItem.objects.filter(pk=item.pk).update(stock=F('stock') - 1)

            pr.status      = PurchaseRequest.Status.APPROVED
            pr.decided_by  = request.user
            pr.decided_at  = timezone.now()
            pr.save(update_fields=['status', 'decided_by', 'decided_at'])

            log_activity(request.user, ActivityLog.Action.UPDATE, 'PurchaseRequest', pr.pk, str(pr),
                         changes={'status': {'old': 'pending', 'new': 'approved'},
                                  'kumush_deducted': price,
                                  'balance_before': txn.balance_before, 'balance_after': txn.balance_after},
                         request=request)

        return Response(self.get_serializer(pr).data)

    @action(detail=True, methods=['post'], permission_classes=[IsStoreManager])
    def reject(self, request, pk=None):
        reason = (request.data.get('reason') or '').strip()
        with transaction.atomic():
            try:
                pr = PurchaseRequest.objects.select_for_update().get(pk=pk)
            except PurchaseRequest.DoesNotExist:
                return Response({'detail': "So'rov topilmadi."}, status=status.HTTP_404_NOT_FOUND)
            if pr.status != PurchaseRequest.Status.PENDING:
                return Response({'detail': "Bu so'rov allaqachon hal qilingan."},
                                 status=status.HTTP_400_BAD_REQUEST)

            pr.status            = PurchaseRequest.Status.REJECTED
            pr.decided_by        = request.user
            pr.decided_at        = timezone.now()
            pr.rejection_reason  = reason
            pr.save(update_fields=['status', 'decided_by', 'decided_at', 'rejection_reason'])

            log_activity(request.user, ActivityLog.Action.UPDATE, 'PurchaseRequest', pr.pk, str(pr),
                         changes={'status': {'old': 'pending', 'new': 'rejected'}, 'reason': reason},
                         request=request)

        return Response(self.get_serializer(pr).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """O'quvchi o'zining hali hal qilinmagan (PENDING) so'rovini bekor
        qiladi. Faqat egasi, faqat PENDING — Kumush yechilmagan, qoldiq
        o'zgarmagan, moliyaviy tranzaksiya yaratilmaydi (hali hech narsa
        sarflanmagan)."""
        student = getattr(request.user, 'student_profile', None)
        with transaction.atomic():
            try:
                pr = PurchaseRequest.objects.select_for_update().get(pk=pk)
            except PurchaseRequest.DoesNotExist:
                return Response({'detail': "So'rov topilmadi."}, status=status.HTTP_404_NOT_FOUND)
            # IDOR himoyasi: faqat so'rov egasi (talaba) bekor qila oladi —
            # admin/developer ham bu action orqali bekor qila olmaydi
            # (spetsifikatsiya: "student can cancel own PENDING request only").
            if not student or pr.student_id != student.id:
                return Response({'detail': "Bu so'rovni bekor qilish huquqingiz yo'q."},
                                 status=status.HTTP_403_FORBIDDEN)
            if pr.status != PurchaseRequest.Status.PENDING:
                return Response({'detail': "Faqat kutilayotgan so'rovlarni bekor qilish mumkin."},
                                 status=status.HTTP_400_BAD_REQUEST)

            pr.status       = PurchaseRequest.Status.CANCELLED
            pr.cancelled_at = timezone.now()
            pr.save(update_fields=['status', 'cancelled_at'])

            log_activity(request.user, ActivityLog.Action.UPDATE, 'PurchaseRequest', pr.pk, str(pr),
                         changes={'status': {'old': 'pending', 'new': 'cancelled'}}, request=request)

        return Response(self.get_serializer(pr).data)

    @action(detail=True, methods=['post'], permission_classes=[IsStoreManager])
    def refund(self, request, pk=None):
        """ADMIN/DEVELOPER — allaqachon berilgan (APPROVED) xaridni qaytaradi:
        Kumush va ombordagi qoldiq tiklanadi, EARN tranzaksiyasi va
        ActivityLog yoziladi. Faqat APPROVED holatidan, va faqat bir marta —
        PENDING/REJECTED qaytarib bo'lmaydi, REFUNDED yana qaytarib bo'lmaydi."""
        reason = (request.data.get('reason') or '').strip()
        with transaction.atomic():
            try:
                pr = PurchaseRequest.objects.select_for_update().get(pk=pk)
            except PurchaseRequest.DoesNotExist:
                return Response({'detail': "So'rov topilmadi."}, status=status.HTTP_404_NOT_FOUND)
            if pr.status != PurchaseRequest.Status.APPROVED:
                return Response({'detail': "Faqat tasdiqlangan (berilgan) xaridlarni qaytarish mumkin."},
                                 status=status.HTTP_400_BAD_REQUEST)

            student = Student.objects.select_for_update().get(pk=pr.student_id)
            item    = StoreItem.objects.select_for_update().get(pk=pr.item_id)
            price   = pr.price_at_request

            full_reason = f"{item.name} qaytarildi" + (f": {reason}" if reason else '')
            txn = student.apply_kumush_and_xp(
                coins_delta=price, reason=full_reason, created_by=request.user,
                source_type='store_refund', source_id=str(pr.pk),
            )
            if txn is not None:
                KumushTransaction.objects.filter(pk=txn.pk).update(purchase=pr)
            StoreItem.objects.filter(pk=item.pk).update(stock=F('stock') + 1)

            pr.status        = PurchaseRequest.Status.REFUNDED
            pr.refunded_at   = timezone.now()
            pr.refunded_by   = request.user
            pr.refund_reason = reason
            pr.save(update_fields=['status', 'refunded_at', 'refunded_by', 'refund_reason'])

            log_activity(request.user, ActivityLog.Action.UPDATE, 'PurchaseRequest', pr.pk, str(pr),
                         changes={'status': {'old': 'approved', 'new': 'refunded'},
                                  'kumush_restored': price, 'stock_restored': 1, 'reason': reason},
                         request=request)

        return Response(self.get_serializer(pr).data)


class KumushTransactionListView(generics.ListAPIView):
    """GET /api/v1/store/transactions/ — Kumush tarixi (student o'ziniki, admin/developer hammasi)."""
    serializer_class    = KumushTransactionSerializer
    permission_classes  = [IsStudentOrStoreManager]
    filter_backends     = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields    = ['student', 'type']
    ordering             = ['-created_at']

    def get_queryset(self):
        qs = KumushTransaction.objects.select_related('student__user')
        u = self.request.user
        if u.is_admin or u.is_developer:
            return qs
        student = getattr(u, 'student_profile', None)
        return qs.filter(student=student) if student else qs.none()


class ManualKumushAdjustmentView(APIView):
    """
    POST /api/v1/store/kumush-adjustment/ — ADMIN/DEVELOPER'ning qo'lda
    Kumush tuzatishi (masalan: xato tuzatish, maxsus mukofot). Student.coins
    to'g'ridan-to'g'ri tahrirlanmaydi — faqat shu endpoint orqali, har doim
    atomik, balansni tekshirib, ledger yozuvi (created_by/balance_before/
    balance_after bilan) va ActivityLog bilan birga.
    """
    permission_classes = [IsStoreManager]

    def post(self, request):
        ser = ManualKumushAdjustmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        student = ser.validated_data['student']
        amount  = ser.validated_data['amount']
        reason  = ser.validated_data['reason']

        txn = student.apply_kumush_and_xp(
            coins_delta=amount, reason=reason, created_by=request.user,
            source_type='manual', source_id='',
        )
        if txn is None:
            return Response(
                {'detail': "O'quvchining Kumushi yetarli emas — balans manfiy bo'lib qoladi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_activity(
            request.user, ActivityLog.Action.UPDATE, 'KumushTransaction', txn.pk, str(txn),
            changes={
                'student': student.full_name, 'amount': amount, 'reason': reason,
                'balance_before': txn.balance_before, 'balance_after': txn.balance_after,
            },
            request=request,
        )
        return Response(KumushTransactionSerializer(txn).data, status=status.HTTP_201_CREATED)


class StoreSummaryView(APIView):
    """GET /api/v1/store/summary/ — Admin dashboard uchun umumiy ko'rsatkichlar."""
    permission_classes = [IsStoreManager]

    def get(self, request):
        items = StoreItem.objects.all()
        requests_qs = PurchaseRequest.objects.all()
        redeemed = KumushTransaction.objects.filter(
            type=KumushTransaction.Type.SPEND
        ).aggregate(total=Sum('amount'))['total'] or 0
        return Response({
            'total_items':        items.count(),
            'active_items':       items.filter(is_active=True).count(),
            'out_of_stock_items': items.filter(stock=0).count(),
            'pending_requests':   requests_qs.filter(status=PurchaseRequest.Status.PENDING).count(),
            'approved_purchases': requests_qs.filter(status=PurchaseRequest.Status.APPROVED).count(),
            'rejected_requests':  requests_qs.filter(status=PurchaseRequest.Status.REJECTED).count(),
            'total_kumush_redeemed': abs(redeemed),
        })


class KumushReportView(APIView):
    """
    GET /api/v1/store/kumush-report/ — ADMIN/DEVELOPER uchun Kumush moliyaviy
    hisoboti: jami berilgan/sarflangan, manba bo'yicha taqsimot, eng ko'p
    ishlaganlar, eng ko'p sotilgan buyumlar, holat bo'yicha so'rovlar soni.
    XP leaderboard'dan farqli — bu faqat Kumush (moliyaviy) statistikasi.
    """
    permission_classes = [IsStoreManager]

    def get(self, request):
        earn_total = KumushTransaction.objects.filter(
            type=KumushTransaction.Type.EARN
        ).aggregate(total=Sum('amount'))['total'] or 0
        spend_total = KumushTransaction.objects.filter(
            type=KumushTransaction.Type.SPEND
        ).aggregate(total=Sum('amount'))['total'] or 0

        def _source_sum(*, startswith=None, exact=None):
            qs = KumushTransaction.objects.all()
            qs = qs.filter(source_type__startswith=startswith) if startswith else qs.filter(source_type=exact)
            return qs.aggregate(total=Sum('amount'))['total'] or 0

        by_source = {
            'attendance': _source_sum(startswith='attendance'),
            'homework':   _source_sum(exact='homework'),
            'zukko':      _source_sum(startswith='zukko'),
            'manual':     _source_sum(exact='manual'),
            'refunded':   _source_sum(exact='store_refund'),
        }

        top_earners = list(
            KumushTransaction.objects.filter(type=KumushTransaction.Type.EARN)
            .values('student_id', 'student__user__full_name')
            .annotate(total_earned=Sum('amount'))
            .order_by('-total_earned')[:10]
        )
        best_selling_products = list(
            PurchaseRequest.objects.filter(status=PurchaseRequest.Status.APPROVED)
            .values('item_id', 'item__name')
            .annotate(purchase_count=Count('id'))
            .order_by('-purchase_count')[:10]
        )
        status_counts = dict(
            PurchaseRequest.objects.values_list('status').annotate(c=Count('id'))
        )
        purchase_counts_by_status = {
            s: status_counts.get(s, 0) for s, _ in PurchaseRequest.Status.choices
        }

        return Response({
            'total_issued': earn_total,
            'total_spent': abs(spend_total),
            'net_outstanding': earn_total + spend_total,
            'by_source': by_source,
            'top_earners': [
                {
                    'student_id': row['student_id'],
                    'student_name': row['student__user__full_name'],
                    'total_earned': row['total_earned'],
                }
                for row in top_earners
            ],
            'best_selling_products': [
                {
                    'item_id': row['item_id'],
                    'item_name': row['item__name'],
                    'purchase_count': row['purchase_count'],
                }
                for row in best_selling_products
            ],
            'purchase_counts_by_status': purchase_counts_by_status,
        })
