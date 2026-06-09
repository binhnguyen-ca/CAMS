-- CAMS SNAPSHOT theo campaign — TAT CA marketer Crossian (1 dong/campaign cho cua so ngay).
-- Goc: query canonical dashboard campaign (uid aevqvkupwlkowe, panel 2) cua CA, da bo cac lock.
-- cam (ad_stats_campaign): spent + daily_budget + status + impressions/clicks
-- w   (ad_stats_ad):       tk metrics that (view/initcheckout/purchase/revenue)
-- Budget = cp.daily_budget/100 (gia tri HIEN TAI -> snapshot moi gio = timeline budget that).
-- Crossian guard: cp.publisher_email like '%@crossian.com' (BO lock 1 email + 2 ad-account + pbase IN).
-- Them: cp.publisher_email AS marketer (DIM). $__timeFrom()/$__timeTo() = cua so HOM NAY (body from/to).
with
w as (
    select date(date_trunc('day'::text, timezone('america/anchorage'::text, timezone('utc'::text, adstats.time))))::varchar as time_report,
        cp.id campaign_id,
        sum(coalesce(adstats.tk_stats_view, 0))            as content_view,
        sum(coalesce(adstats.tk_stats_initcheckout, 0))    as initial_checkout,
        sum(coalesce(adstats.tk_stats_purchase, 0))        as purchase,
        sum(coalesce(adstats.tk_stats_revenue, 0)) - sum(coalesce(adstats.tk_stats_tax_amount, 0)) as transaction_revenue
    from ad_stats_ad adstats
        left join fb_adset adset ON adset.id = adstats.adset_id
        left join fb_campaign cp ON cp.id = adstats.campaign_id
    where date_trunc('day'::text, timezone('america/anchorage'::text, timezone('utc'::text, adstats.time))) between ($__timeFrom() at time zone 'america/anchorage') and ($__timeTo() at time zone 'america/anchorage')
        and adstats.campaign_id is not null
        and adset.campaign_id is not null
        and cp.publisher_email like '%@crossian.com'
        and cp.effective_status = ANY(ARRAY['ACTIVE','PAUSED','DELETED','ARCHIVED','IN_PROCESS','WITH_ISSUES'])
    GROUP BY date_trunc('day'::text, timezone('america/anchorage'::text, timezone('utc'::text, adstats.time))), cp.id
),
cam as (
    select date(date_trunc('day'::text, timezone('america/anchorage'::text, timezone('utc'::text, adstats.time))))::varchar as time_report,
        cp.name campaign_name,
        cp.pbase_code pbase_code,
        cp.publisher_email publisher_email,
        cp.id campaign_id,
        sum(coalesce(adstats.stats_spend, 0))      as spent,
        cp.daily_budget / 100                      as daily_budget,
        cp.effective_status                        as campaign_status,
        sum(coalesce(adstats.stats_click, 0))      as link_clicks,
        sum(adstats.stats_impression)              as impressions
    from ad_stats_campaign adstats
        left join fb_campaign cp ON cp.id = adstats.campaign_id
    where date_trunc('day'::text, timezone('america/anchorage'::text, timezone('utc'::text, adstats.time))) between ($__timeFrom() at time zone 'america/anchorage') and ($__timeTo() at time zone 'america/anchorage')
        and adstats.campaign_id is not null
        and cp.publisher_email like '%@crossian.com'
        and cp.effective_status = ANY(ARRAY['ACTIVE','PAUSED','DELETED','ARCHIVED','IN_PROCESS','WITH_ISSUES'])
    GROUP BY date_trunc('day'::text, timezone('america/anchorage'::text, timezone('utc'::text, adstats.time))), cp.id, cp.name, cp.pbase_code, cp.publisher_email, cp.daily_budget, cp.effective_status
)
select
    cam.campaign_id                          as campaign_id,
    cam.publisher_email                      as marketer,
    cam.campaign_name                        as campaign_name,
    cam.pbase_code                           as product,
    cam.campaign_status                      as effective_status,
    cam.daily_budget                         as budget,
    cam.spent                                as me,
    coalesce(w.transaction_revenue, 0)       as rev,
    coalesce(w.purchase, 0)                  as po,
    cam.impressions                          as impressions,
    cam.link_clicks                          as clicks,
    coalesce(w.content_view, 0)              as views,
    coalesce(w.initial_checkout, 0)          as init_checkout
from cam
    left join w on w.campaign_id = cam.campaign_id and w.time_report = cam.time_report
order by cam.spent desc
