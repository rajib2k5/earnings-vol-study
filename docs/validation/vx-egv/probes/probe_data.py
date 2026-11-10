import sys, datetime; _dt0 = datetime.date(2020,1,2);
import sys; sys.path.insert(0, '/home/rajib2k5/dev/earnings-vol-study/docs/validation/vx-egv/probes')
from common import *
claim = sys.argv[1]; mode = sys.argv[2] if len(sys.argv) > 2 else 'normal'
D = load(mode); fail = []
if claim == 'C5':   # level ratio (CLOSE-read)/cm30_blind_iv must be near 1 for each name
    for nm, d in D.items():
        ok = np.isfinite(d['vx']) & np.isfinite(d['blind']) & (d['blind'] > 0)
        r = np.median(d['vx'][ok] / d['blind'][ok]); print(nm, 'n', ok.sum(), 'median ratio', round(r, 4),
              'median vx', round(np.median(d['vx'][ok]), 4), 'median blind', round(np.median(d['blind'][ok]), 4))
        if not 0.7 <= r <= 1.5: fail.append(nm)
elif claim == 'C6':  # lag 0 must have the highest corr of daily changes, per name and pooled
    pooled = {-1: [], 0: [], 1: []}
    for nm, d in D.items():
        rs = {}
        for L in (-1, 0, 1):
            r, n, dx, dy = chg_corr(d['blind'], d['vx'], L); rs[L] = r; pooled[L].append((dx, dy))
        print(nm, {k: round(v, 4) for k, v in rs.items()})
        if not (rs[0] > rs[-1] and rs[0] > rs[1]): fail.append(nm)
    pr = {L: np.corrcoef(np.concatenate([a for a, b in v]), np.concatenate([b for a, b in v]))[0, 1] for L, v in pooled.items()}
    print('pooled', {k: round(v, 4) for k, v in pr.items()})
    if not (pr[0] > pr[-1] and pr[0] > pr[1]): fail.append('pooled')
elif claim == 'C7':  # coverage per file over the span of cm30_blind_iv
    for nm, d in D.items():
        have = np.isfinite(d['blind'])
        idx = np.flatnonzero(have); lo = ses_i = d['ses'].index(_dt0); hi = idx[-1]
        span = np.arange(lo, hi + 1)
        # all sessions of the span (calendar), not just ours
        cov = np.isfinite(d['vx'][span]).mean()
        covours = np.isfinite(d['vx'][have]).mean()
        print(nm, 'span', d['ses'][lo], d['ses'][hi], 'sessions', len(span), 'cboe cov of span %.4f' % cov, 'cboe cov on our sessions %.4f' % covours,
              'vx missing sessions', int((~np.isfinite(d['vx'][span])).sum()), [str(d['ses'][i]) for i in span[~np.isfinite(d['vx'][span])]], 'ours missing', int((~have[span]).sum()))
        if cov < 0.9: fail.append(nm)
elif claim == 'C1C2':  # 30d VIX-style index sits above ATM IV on most days; tracks blind better than front; no jump at expiry roll
    for nm, d in D.items():
        ok = np.isfinite(d['vx']) & np.isfinite(d['blind'])
        above = (d['vx'][ok] > d['blind'][ok]).mean()
        okf = ok & np.isfinite(d['front'])
        rb = chg_corr(d['blind'], d['vx'])[0]; rf = chg_corr(d['front'], d['vx'])[0]
        lb = np.corrcoef(d['vx'][okf], d['blind'][okf])[0, 1]; lf = np.corrcoef(d['vx'][okf], d['front'][okf])[0, 1]
        # roll days: front_expiry changes
        ses = d['ses']; pos = {x: i for i, x in enumerate(ses)}
        pi = np.array([pos[x] for x in d['sub'].index])
        # monthly roll: first session after the third Friday of a month (standard VIX-style roll)
        import datetime as _dt
        def third_fri(y, m):
            d1 = _dt.date(y, m, 1); f = d1 + _dt.timedelta(days=(4 - d1.weekday()) % 7); return f + _dt.timedelta(days=14)
        tf = {third_fri(y, m) for y in range(2020, 2027) for m in range(1, 13)}
        roll = np.array([i > 0 and ses[p - 1] in tf for i, p in enumerate(pi)])
        dv = np.full(len(ses), np.nan); lv = np.log(np.where(d['vx'] > 0, d['vx'], np.nan)); dv[1:] = lv[1:] - lv[:-1]
        dfr = np.full(len(ses), np.nan); lf_ = np.log(np.where(d['front'] > 0, d['front'], np.nan)); dfr[1:] = lf_[1:] - lf_[:-1]
        sp = d['sub']['sessions_since_prev_event'].values; sn = d['sub']['sessions_to_next_event'].values
        clean = ~((sp <= 3) | (sn <= 3) | ((sn >= 18) & (sn <= 25)))   # drop days within 3 sessions of an earnings event (confound: IBM reports right after 3rd Friday)
        print(nm, 'roll days', int(roll.sum()), 'of which near earnings or entering the 30d window (18-25 sessions ahead)', int((roll & ~clean).sum()))
        roll = roll & clean
        rolled = pi[roll]
        nonroll = np.setdiff1d(pi[clean], rolled); nonroll = np.array([p for p in nonroll if ses[p].weekday() == 0])  # control: other Mondays (roll day is a Monday after a weekend gap)
        jv_roll = np.nanmedian(np.abs(dv[rolled])); jv_non = np.nanmedian(np.abs(dv[nonroll]))
        jf_roll = np.nanmedian(np.abs(dfr[rolled])); jf_non = np.nanmedian(np.abs(dfr[nonroll]))
        print(nm, 'share vx>blind %.3f' % above, '| dlog corr blind %.3f front %.3f | level corr blind %.3f front %.3f' % (rb, rf, lb, lf),
              '| n_roll', len(rolled), '| median|dlnVX| roll %.4f nonroll %.4f ratio %.2f' % (jv_roll, jv_non, jv_roll / jv_non),
              '| median|dln front| roll %.4f nonroll %.4f ratio %.2f' % (jf_roll, jf_non, jf_roll / jf_non))
        if above < 0.5: fail.append(nm + ':above')
        if rb <= rf: fail.append(nm + ':track')
        if jv_roll / jv_non > 1.5: fail.append(nm + ':rolljump')
print('FAIL' if fail else 'PASS', fail); sys.exit(1 if fail else 0)
