from django.contrib import admin

from .models import (
    Category,
    Member,
    Pay,
    Place,
    Schedule,
    SchedulePlace,
    Travel,
    TravelCategory,
    TravelDayPlan,
)


# =========================================================
# Admin 사이트 제목
# =========================================================

admin.site.site_header = "TRIPA 관리자"
admin.site.site_title = "TRIPA Admin"
admin.site.index_title = "TRIPA 서비스 관리"


# =========================================================
# Inline
# =========================================================

class TravelDayPlanInline(admin.TabularInline):
    model = TravelDayPlan
    extra = 0
    fields = (
        "plan_date",
        "accommodation_name",
        "arrival_time",
        "departure_time",
    )
    ordering = ("plan_date",)


class TravelCategoryInline(admin.TabularInline):
    model = TravelCategory
    extra = 0
    autocomplete_fields = ("category",)


class PlaceInline(admin.TabularInline):
    model = Place
    extra = 0
    fields = (
        "p_name",
        "p_addr",
        "p_kind",
    )
    show_change_link = True


class ScheduleInline(admin.TabularInline):
    model = Schedule
    extra = 0
    fields = ("s_day",)
    ordering = ("s_day",)
    show_change_link = True


class SchedulePlaceInline(admin.TabularInline):
    model = SchedulePlace
    extra = 0
    autocomplete_fields = ("place",)
    fields = (
        "visit_order",
        "place",
        "arrive_time",
        "stay_time",
        "start_time",
        "travel_time",
    )
    ordering = ("visit_order",)


class PayInline(admin.TabularInline):
    model = Pay
    extra = 0
    autocomplete_fields = ("place",)
    fields = (
        "pay_context",
        "pay_pay",
        "place",
    )


# =========================================================
# 회원
# =========================================================

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "m_id",
        "email",
        "nickname",
        "name",
        "travel_count",
    )
    search_fields = (
        "email",
        "nickname",
        "name",
    )
    ordering = ("m_id",)

    @admin.display(description="여행 수")
    def travel_count(self, obj):
        return obj.travels.count()


# =========================================================
# 여행
# =========================================================

@admin.register(Travel)
class TravelAdmin(admin.ModelAdmin):
    list_display = (
        "t_id",
        "t_title",
        "member",
        "t_place",
        "t_way",
        "t_start",
        "t_end",
        "t_budget",
    )
    list_filter = (
        "t_way",
        "t_start",
        "t_end",
    )
    search_fields = (
        "t_title",
        "t_place",
        "member__email",
        "member__nickname",
    )
    autocomplete_fields = ("member",)
    ordering = ("-t_id",)
    date_hierarchy = "t_start"

    fieldsets = (
        (
            "기본 여행 정보",
            {
                "fields": (
                    "member",
                    "t_title",
                    "t_place",
                    "t_way",
                    "t_start",
                    "t_end",
                    "t_day",
                    "t_budget",
                )
            },
        ),
        (
            "출발 정보",
            {
                "fields": (
                    "start_place",
                    "start_addr",
                    "start_lat",
                    "start_lon",
                    "start_time",
                )
            },
        ),
        (
            "숙소 / 복귀 정보",
            {
                "fields": (
                    "accommodation",
                    "accommodation_lat",
                    "accommodation_lon",
                    "checkin_time",
                    "return_time",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = (
        TravelDayPlanInline,
        TravelCategoryInline,
        PlaceInline,
        ScheduleInline,
    )


# =========================================================
# 날짜별 여행 계획
# =========================================================

@admin.register(TravelDayPlan)
class TravelDayPlanAdmin(admin.ModelAdmin):
    list_display = (
        "tdp_id",
        "travel",
        "plan_date",
        "accommodation_name",
        "arrival_time",
        "departure_time",
    )
    list_filter = ("plan_date",)
    search_fields = (
        "travel__t_title",
        "accommodation_name",
        "accommodation_addr",
    )
    autocomplete_fields = ("travel",)
    ordering = ("-plan_date",)


# =========================================================
# 카테고리
# =========================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "c_id",
        "c_name",
    )
    search_fields = ("c_name",)
    ordering = ("c_id",)


@admin.register(TravelCategory)
class TravelCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "tc_id",
        "travel",
        "category",
    )
    list_filter = ("category",)
    search_fields = (
        "travel__t_title",
        "category__c_name",
    )
    autocomplete_fields = (
        "travel",
        "category",
    )


# =========================================================
# 장소
# =========================================================

@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = (
        "p_id",
        "p_name",
        "travel",
        "p_kind",
        "p_addr",
    )
    list_filter = ("p_kind",)
    search_fields = (
        "p_name",
        "p_addr",
        "p_kind",
        "travel__t_title",
    )
    autocomplete_fields = ("travel",)
    ordering = ("-p_id",)


# =========================================================
# 일정
# =========================================================

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "s_id",
        "travel",
        "s_day",
        "place_count",
        "pay_total",
    )
    list_filter = ("s_day",)
    search_fields = (
        "travel__t_title",
        "travel__member__email",
    )
    autocomplete_fields = ("travel",)
    ordering = ("-s_day",)
    date_hierarchy = "s_day"

    inlines = (
        SchedulePlaceInline,
        PayInline,
    )

    @admin.display(description="장소 수")
    def place_count(self, obj):
        return obj.schedule_places.count()

    @admin.display(description="DAY 비용")
    def pay_total(self, obj):
        total = sum(
            pay.pay_pay or 0
            for pay in obj.payments.all()
        )
        return f"{total:,}원"


# =========================================================
# 일정 장소
# =========================================================

@admin.register(SchedulePlace)
class SchedulePlaceAdmin(admin.ModelAdmin):
    list_display = (
        "sp_id",
        "schedule",
        "visit_order",
        "place",
        "arrive_time",
        "stay_time_display_admin",
        "start_time",
        "travel_time_display",
    )
    list_filter = (
        "schedule__s_day",
        "place__p_kind",
    )
    search_fields = (
        "place__p_name",
        "place__p_addr",
        "schedule__travel__t_title",
    )
    autocomplete_fields = (
        "schedule",
        "place",
    )
    ordering = (
        "schedule__s_day",
        "visit_order",
    )

    @admin.display(description="체류시간")
    def stay_time_display_admin(self, obj):
        return obj.stay_time_display

    @admin.display(description="이동시간")
    def travel_time_display(self, obj):
        if obj.travel_time is None:
            return "-"

        hours, minutes = divmod(
            obj.travel_time,
            60,
        )

        if hours and minutes:
            return f"{hours}시간 {minutes}분"

        if hours:
            return f"{hours}시간"

        return f"{minutes}분"


# =========================================================
# 비용
# =========================================================

@admin.register(Pay)
class PayAdmin(admin.ModelAdmin):
    list_display = (
        "pay_id",
        "pay_context",
        "formatted_pay",
        "schedule",
        "place",
    )
    list_filter = (
        "schedule__s_day",
    )
    search_fields = (
        "pay_context",
        "place__p_name",
        "schedule__travel__t_title",
    )
    autocomplete_fields = (
        "schedule",
        "place",
    )
    ordering = ("-pay_id",)

    @admin.display(description="금액")
    def formatted_pay(self, obj):
        return f"{obj.pay_pay or 0:,}원"
