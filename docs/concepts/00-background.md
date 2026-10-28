# Background: earnings announcements, implied volatility and event studies

Literature background for `earnings-vol-study`. Researched and written on 2026-10-28. It should take about 35 minutes to read.

## How to read this document

Every statement carries one of three labels:

- **Reported:** what a paper says. Each one has a reference number [n]. The reference list says how much of each source I actually read: the full text, the abstract only, or the bibliographic record only.
- **Derived:** maths or numbers I worked out myself. They are not from a paper unless the text says so. Check them.
- **Open:** a question this project has to answer with its own data.

This document is background for decisions recorded elsewhere. The project's choices are in the ADRs: [0002 day 0](../adr/0002-day-zero-convention.md), [0003 IV measures](../adr/0003-iv-measures.md), [0004 windows and abnormal IV](../adr/0004-baseline-and-event-windows.md) and [0005 tests](../adr/0005-statistical-test-suite.md). When this document lists options, the ADR it names says which one was chosen. Two naming differences to keep in mind: the ADRs call the event variance $E$, which is $\sigma_E^2$ here. They also define abnormal IV as $\text{ALIV}$ (log, VIX-adjusted) and $\text{AIV}$ (vol points, display only).

Notation used throughout:

| Symbol | Meaning |
|---|---|
| $t$ | today |
| $\tau$ | event time in trading days; $\tau = 0$ is the day the price reacts to the announcement |
| $T$ | time left to an option's expiry, in years |
| $\sigma$ | an annualised implied volatility (IV) |
| $w = \sigma^2 T$ | total implied variance to expiry |
| $\sigma_d$ | ordinary ("diffusive") volatility, annualised |
| $\sigma_E$ | standard deviation of the earnings jump in log price. This is **not** annualised. |
| $N$ | number of events in a sample |

---

## 0. The story in one paragraph

An earnings date is known in advance. The size and sign of the reaction are not. So the market knows that one big day is coming, and roughly when. Any option that expires after that date has to price it. One big day adds a lot of *annualised* volatility to a short-dated option and very little to a long-dated one. That one fact explains three patterns: short-dated IV rises as the date gets closer, the term structure slopes down before earnings, and IV "crushes" once the news is out. This project runs an event study on top of that: how big is the crush, is it unusual compared with ordinary IV moves, and what drives it across firms? The standard tools were built for stock returns. They need adapting, because IV does not behave like a return (§9).

---

## 1. Why IV rises before earnings and collapses after

### 1.1 Intuition

Variances add up across independent pieces of time. Think of the log return from today to expiry as many ordinary days plus one special day. Each ordinary day adds $\sigma_d^2\,\Delta t$ of variance. The earnings day adds an extra lump, $\sigma_E^2$. An option only sees the total.

### 1.2 The model (Reported: [3], [1])

Patell and Wolfson treated the announcement as a short, known burst of extra variance (as described in [3]). Dubinsky and Johannes [3] treat it as a jump in the log price on a known date, with a random size drawn from a normal distribution. In the simplest version (Black–Scholes plus one such jump), an option that expires after the event satisfies:

$$
\sigma_{IV}^2(T)\,T = \sigma_d^2\,T + \sigma_E^2
\qquad\Longleftrightarrow\qquad
\sigma_{IV}^2(T) = \sigma_d^2 + \frac{\sigma_E^2}{T}
$$

- $\sigma_{IV}(T)$ is the Black–Scholes IV of the option with $T$ years left.
- $\sigma_d^2 T$ is the variance from ordinary days.
- $\sigma_E^2$ is the variance of the earnings jump. It is a total amount, not a rate.

The jump is normal and its date is fixed, so the log price at expiry is still normal. The Black–Scholes formula therefore still holds, using this total variance [3].

[3] draws three consequences:

1. **Run-up.** Fix the expiry date and let time pass. $T$ shrinks, so $\sigma_E^2/T$ grows. IV rises into the event, roughly in proportion to $1/T$.
2. **Crush.** Once the event has passed, the jump term is gone and IV falls straight to about $\sigma_d$. In variance units the drop is $\sigma_E^2/T$, so the shortest-dated options crush the hardest.
3. **Downward-sloping term structure.** Before the event, a longer expiry spreads the same $\sigma_E^2$ over more time, so its IV is lower.

**Reported example [3].** Intel announced after the close on 15 July 1997. Just before, the at-the-money July call (about 5 trading days left) had IV of 71.15%, and the August call (about 25 trading days left) had 45.19%. The next day the July IV had fallen to 42.96%.

**Reported, broad sample [11].** In Gao, Xing and Zhang's working-paper version, average straddle IV rises from 0.467 at day −30 to 0.514 at day −1, stays at 0.506 on day 0, and drops to 0.464 on day +1. Their day 0 is the I/B/E/S announcement date, with no adjustment for announcements made before the open or after the close.

### 1.3 Extracting the event variance from two expiries (Derived; it matches [3])

Take two expiries, $T_1 < T_2$. Both must fall after this announcement and before the next one. Their ATM IVs are $\sigma_1$ and $\sigma_2$. Assume the same ordinary volatility $\sigma_d$ applies to both. Then:

$$
\sigma_1^2 T_1 = \sigma_d^2 T_1 + \sigma_E^2,
\qquad
\sigma_2^2 T_2 = \sigma_d^2 T_2 + \sigma_E^2 .
$$

That is two equations in two unknowns. Subtract the first from the second:

$$
\sigma_d^2 = \frac{\sigma_2^2 T_2 - \sigma_1^2 T_1}{T_2 - T_1} .
$$

This is the **forward variance rate** between $T_1$ and $T_2$: the ordinary rate the market expects once the event is out of the way. Put it back into the first equation:

$$
\sigma_E^2 \;=\; \sigma_1^2 T_1 - \sigma_d^2 T_1
\;=\; T_1\,\frac{\sigma_1^2 (T_2 - T_1) - \sigma_2^2 T_2 + \sigma_1^2 T_1}{T_2 - T_1}
\;=\; \frac{T_1 T_2\,(\sigma_1^2 - \sigma_2^2)}{T_2 - T_1} .
$$

So the formula in the project brief is correct. Dubinsky and Johannes write it as $(\sigma_1^2 - \sigma_2^2)/(1/T_1 - 1/T_2)$ [3]. Multiply the top and bottom by $T_1T_2$ and it is the same expression.

In plain English: take the post-event variance rate and project it back to today. Whatever total variance the short option still has left over is the event.

I recomputed two published examples:

- **Intel.** With [3]'s inputs ($T_1 = 0.0198$, $T_2 = 0.0992$ years, IVs of 71.15% and 45.19%), I get $\sigma_E = 8.64\%$. [3] reports 8.6%. The implied ordinary volatility comes out at $\sigma_d \approx 35.9\%$.
- **GBP/USD the day before the Brexit vote**, from the authors' 2017 slides [5]. The 1-month IV was 28.21% and the 2-month IV was 21.51%. With $T = 1/12$ and $2/12$, I get $\sigma_E = 7.45\%$. The slides report 7.5% and note that spot fell about 10% the next day.

**Ex-post estimator (Reported: [3]).** Compare the same option's IV just before and just after the announcement: $\sigma_E^2 = T\,(\sigma_{pre}^2 - \sigma_{post}^2)$. Applied to the Intel July option ($T = 0.0198$, IV from 71.15% to 42.96%), I get 8.0%, but [3] reports 7.2%. **Derived:** the two reconcile if $T = 4/252$ instead of $5/252$. That gives 7.15%, and the $T$ that gives exactly 7.2% is 4.06 trading days, so [3] apparently counted four trading days for this estimator (re-checked in the milestone-0 methodology review). Across 20 firms from 1996 to 2002, [3] reports mean $\sigma_E$ of 10.4% from the term-structure estimator and 8.5% from the ex-post one.

### 1.4 The implied move (Derived)

$\sigma_E$ is the standard deviation of the log-price jump $J$. If $J$ is normal with mean close to 0, its expected absolute size is:

$$
\mathbb{E}\big[\lvert J\rvert\big] = \sigma_E\sqrt{2/\pi} \approx 0.80\,\sigma_E .
$$

For Intel that is $0.80 \times 8.64\% \approx 6.9\%$.

Traders often quote a different "implied move": the price of the front-month ATM straddle divided by spot. For an option struck at the forward, the Black–Scholes call price is $S[2\Phi(\sigma\sqrt{T}/2) - 1] \approx S\sigma\sqrt{T}/\sqrt{2\pi}$, where $\Phi$ is the standard normal CDF. A straddle is about twice that, so straddle/spot $\approx 0.80\,\sigma\sqrt{T} = 0.80\sqrt{\sigma_d^2 T + \sigma_E^2}$. This approximation is usually credited to Brenner and Subrahmanyam [10]; I confirmed that paper exists but derived the formula myself. The straddle number includes ordinary variance over the option's whole life, so it overstates the event-only move, and the gap grows with the expiry. **In this project, "implied move" means $\sigma_E$, or $0.80\,\sigma_E$, unless a section says otherwise.**

**The realised counterpart (Reported: [3]).** [3] divides the reaction-day log return by $\sqrt{\sigma_E^2 + \sigma_d^2/252}$, which is the event variance plus one ordinary trading day. If options priced the move fairly, this ratio would have a standard deviation of 1.

### 1.5 Day-count assumptions (Derived, except where cited)

- **Use one clock.** In the Intel example, 5, 25 and 70 business days map to 0.0198, 0.0992 and 0.2778 years. That is trading days divided by 252 [3]. If $T$ and $\sigma$ use the same clock, $\sigma_E^2$ does not depend on the annualisation constant. Rescaling $T$ to $cT$ forces $\sigma^2$ to become $\sigma^2/c$, and the $c$'s cancel in $T_1T_2(\sigma_1^2-\sigma_2^2)/(T_2-T_1)$.
- **Calendar and trading clocks are not just rescalings of each other.** Weekends and holidays count on one clock and not on the other. When the first expiry is only a few days away, the choice changes $T_1/T_2$ and therefore changes $\sigma_E$. Use the convention of whoever computed the IVs. If you compute IVs yourself, a trading-day clock fits the model, in which ordinary variance arrives on trading days.
- **The project's choice.** ADR 0003 counts time in NYSE sessions. In its AAPL worked example, switching to the calendar clock raises $E$ by 36% (0.00088284 to 0.001204), and the implied move $\sqrt E$ by 17% (2.97% to 3.47%).
- **The event day is also an ordinary day.** $\sigma_E^2$ is the *extra* variance. The reaction-day return has total variance $\sigma_E^2 + \sigma_d^2/252$.
- **Before the open or after the close (BMO/AMC).** An announcement made after the close (AMC) on day $d$ moves the price on day $d+1$. One made before the open (BMO) moves it on day $d$. "Before the event" therefore means before the reaction day's open. An option that expires on the afternoon of an AMC announcement does not span the event.

### 1.6 Assumptions and where they break

| Assumption | When it fails | Effect |
|---|---|---|
| Both expiries share one ordinary volatility (the term structure is flat apart from the event) | Stochastic volatility: vol is high and expected to fall, or low and expected to rise | A downward ex-event slope inflates $\sigma_E^2$. An upward slope shrinks it, possibly below zero [3]. |
| Exactly one event before $T_2$ | The next earnings date, an ex-dividend date, an FOMC meeting or a product event falls inside the window | Variance gets attributed to the wrong event |
| Both expiries are after the event and liquid | The first expiry is at or before the event, or short-dated quotes have wide spreads | [3] dropped expiries with less than five days left, then had to rely on longer, noisier ones |
| The jump is normal and ATM IV captures everything | The risk-neutral distribution is bimodal before earnings, which shows up as a "concave" smile [9] | ATM IV misses information that sits in the smile |
| Risk-neutral equals real-world | Never exactly | $\sigma_E$ is a risk-neutral number and includes any risk premium [3] |

**Reported [3].** About 1 in 9 announcements gave a negative estimate, with both methods, and these were set to zero. More than half of those cases arose because the short expiry was too close to the announcement and had to be dropped.

### 1.7 What the papers report

- **Patell and Wolfson (1979)** [1]: call prices before annual earnings show systematic changes in Black–Scholes implied variance. Investors anticipate that the release will move prices. (I read the Stanford GSB summary, not the article.)
- **Patell and Wolfson (1981)** [2]: the same question for quarterly announcements, as the title says. According to [3], they also tracked the rise in IV before the announcement, assuming ordinary volatility stayed constant over about 20 business days. I could not read the paper itself.
- **Donders and Vorst (1996)** [6]: 96 scheduled announcements by 23 Dutch firms, 1991–1992. IV rises before the announcement, peaks on the eve, falls sharply afterwards and drifts back to its normal level. Only the event day's stock return is unusually volatile. (Full text read.)
- **Isakov and Pérignon (2001)** [7]: Swiss data, 1989–1998. Their model has volatility clustering and a leverage effect. It predicts that IV falls after good news but stays flat or rises after bad news, and the data agree. (Abstract only.)
- **Dubinsky and Johannes** [3], later **Dubinsky, Johannes, Kaeck and Seeger (2019)** [4]: the jump-on-a-known-date model, the two estimators above, and evidence that the uncertainty priced ahead of earnings is large, varies over time and predicts realised volatility. I confirmed the RFS paper's details (32(2), 646–687) but read only its abstract and the authors' 2017 slides [5]. **The formulas in this document come from the 2004 working paper.**
- **Ederington and Lee (1996)** [8] is about macro releases, not earnings. Before a scheduled release, implied volatility already contains its expected impact and falls afterwards. Unscheduled news pushes it up. The logic is the same; only the market differs.
- **Alexiou, Goyal, Kostakis and Rompolis (2025)** [9]: just before earnings, short-dated equity IV curves are often concave, meaning the risk-neutral distribution has two humps. Stocks with concave curves move more on the day and are more volatile afterwards. The shape predicts how big the move will be. (Abstract only. The abstract does not say whether the shape also predicts the direction.)

### 1.8 How this project uses it

ADR 0003 puts this section into practice:

- $E$ is computed at day −1 from the two shortest expiries that span the event, using the formula derived in §1.3.
- $E$ is stored with its sign. Group averages are taken in variance space, so events with $E \le 0$ are kept.
- The implied move is $\sqrt E$. The figure compared with $\lvert r_0\rvert$ is $\sqrt{2/\pi}\sqrt{E + \sigma_d^2/252}$, where $\sigma_d$ is annualised as in this document, so $\sigma_d^2/252$ is one session's ordinary variance (ADR 0003 §c, "Units"). That matches the [3] standardisation in §1.4.
- The 30-day IV interpolates only within one class of expiry (all before the event or all after it), so event variance does not leak into the baseline.
- The front fixed-expiry crush is a secondary measure, because its size scales with $1/T$.

---

## 2. Risk premia: is earnings volatility over- or under-priced?

### 2.1 What the papers report

| Paper | Data | Finding, as reported |
|---|---|---|
| Dubinsky and Johannes [3] (WP, full text) | 20 low-dividend firms with the most active options, 1996–2002 | Realised event-day volatility averaged 0.74 of option-implied volatility, or 0.82 using the standardised ratio. So options priced about 20–30% more volatility than was realised, a premium for jump-volatility risk. The gap mostly disappears with the ex-post estimator. Standardised moves look normal, and there is no evidence of a premium on the average direction of the jump. |
| Gao, Xing and Zhang (2018) [11] | Broad US sample, 1996–2013 | Straddles on individual stocks usually lose money. But ATM straddles bought 3 days before and held to the announcement day earn 3.34% on average, which is highly significant. The authors read this as investors **under**-estimating earnings uncertainty, especially for small, volatile, fat-tailed or costly-to-trade firms. |
| Barth and So (2014) [12] | US | Some announcements carry volatility risk that cannot be diversified away. The premium in option prices rises with that exposure, is concentrated in "bellwether" firms, and makes straddle returns around earnings predictable. |
| Alexiou et al. (2025) [9] | US | When pre-earnings IV curves are concave, delta-neutral straddles and strangles, and calendar straddles, earn significantly negative returns. Investors pay to hedge announcement risk. |
| Billings and Jennings (2011) [13] | US | An options-based measure of anticipated information content (AIC) predicts how strongly the stock price will react to the earnings news. |
| Rogers, Skinner and Van Buskirk (2009) [14] | US | Measured with IV, management earnings forecasts raise short-term uncertainty, mainly when the forecast is bad news. Uncertainty falls after earnings announcements, but by less when a negative forecast came first. |
| Neururer, Papadakis and Riedl (2016) [15] | US | Model-free IV falls after earnings on average. It falls less after bigger surprises, and a large enough surprise raises it. |
| Truong, Corrado and Chen (2012) [16] | US, 1996–2008 | In the 3 days after the announcement, the IV change moves opposite to the earnings news, and more strongly for bad news. There is no such relation before or after that window. |

### 2.2 Where they disagree

[3] points towards selling: implied exceeded realised in variance terms, but only for a handful of very liquid names. [11] points towards buying: straddles from day −3 to day 0 made money in a broad sample. [12] and [9] say the premium is real but concentrated in particular firms or particular smile shapes.

Possible reasons follow. **These are my hypotheses, not findings.**

- **Different firms:** 20 mega-caps versus a broad cross-section.
- **Different quantities:** [3] compares variances on the event day. [11] measures straddle profit from day −3, which also captures the pre-event IV run-up.
- **Timing:** [11] uses the I/B/E/S date with no BMO/AMC adjustment, as its working paper states. It also reports windows that end on day +1.
- **Costs:** [11] computes returns at bid–ask midpoints, but real spreads on short-dated options around earnings are wide.

**Open.** In this project's sample, what is the distribution of realised $\lvert r_0\rvert / \sigma_E$, and does it vary with firm size, liquidity and $\sigma_E$ itself? That is a measurement question. It is not a trading recommendation: transaction costs, margin and tail losses are out of scope.

---

## 3. Event-study methodology (MacKinlay 1997; Brown and Warner 1985)

### 3.1 Timeline (Reported: [17])

Event time is $\tau$, with $\tau = 0$ the event day.

- **Estimation window:** $\tau = T_0+1, \dots, T_1$, of length $L_1 = T_1 - T_0$. It is used to learn what "normal" looks like.
- **Event window:** $\tau = T_1+1, \dots, T_2$, of length $L_2 = T_2 - T_1$. This is where we look for the effect.
- The two windows should not overlap, so the event cannot contaminate "normal".

### 3.2 Normal performance and abnormal returns (Reported: [17])

The market model is

$$
R_{i\tau} = \alpha_i + \beta_i R_{m\tau} + \varepsilon_{i\tau},
\qquad \mathbb{E}[\varepsilon_{i\tau}] = 0,
\qquad \operatorname{Var}(\varepsilon_{i\tau}) = \sigma_{\varepsilon_i}^2 .
$$

- $R_{i\tau}$ is the return of security $i$, and $R_{m\tau}$ is the market return.
- $\alpha_i$ and $\beta_i$ are estimated by OLS in the estimation window.

The abnormal return is $AR_{i\tau} = R_{i\tau} - \hat\alpha_i - \hat\beta_i R_{m\tau}$. It is an out-of-sample forecast error. Its variance has two parts, the true noise plus the error from estimating $\alpha$ and $\beta$:

$$
\sigma^2(AR_{i\tau}) = \sigma_{\varepsilon_i}^2\left[1 + \frac{1}{L_1}\left(1 + \frac{(R_{m\tau} - \hat\mu_m)^2}{\hat\sigma_m^2}\right)\right]
$$

- $\hat\mu_m$ and $\hat\sigma_m^2$ are the mean and variance of the market return in the estimation window.

In the JEL scan I read, eq. (8) is printed without the $\sigma_{\varepsilon_i}^2$ factor on the second term. The factor has to be there for the units to work. The second term shrinks as $L_1$ grows. It also makes a security's ARs slightly correlated with each other over time, because they all share the same estimation error.

### 3.3 Aggregation (Reported: [17])

**Through time, for one security:**

$$
CAR_i(\tau_1,\tau_2) = \sum_{\tau=\tau_1}^{\tau_2} AR_{i\tau},
\qquad
\sigma_i^2(\tau_1,\tau_2) \approx (\tau_2 - \tau_1 + 1)\,\sigma_{\varepsilon_i}^2 .
$$

The variance formula assumes that ARs are independent over time. Remember this assumption: it fails for IV (§9).

**Across $N$ events:**

$$
AAR_\tau = \frac{1}{N}\sum_{i=1}^N AR_{i\tau},
\qquad
CAAR(\tau_1,\tau_2) = \sum_{\tau=\tau_1}^{\tau_2} AAR_\tau = \frac{1}{N}\sum_{i=1}^N CAR_i(\tau_1,\tau_2),
$$

$$
\operatorname{Var}(CAAR) = \frac{1}{N^2}\sum_{i=1}^N \sigma_i^2(\tau_1,\tau_2),
\qquad
\theta_1 = \frac{CAAR(\tau_1,\tau_2)}{\operatorname{Var}(CAAR)^{1/2}} \;\overset{\text{approx}}{\sim}\; N(0,1).
$$

This variance formula needs the events to be uncorrelated, which means their event windows must not overlap in calendar time ("no clustering") [17].

### 3.4 The cross-sectional t-test (Reported: [17])

Instead of using the estimation-window variance, use the spread of the event CARs themselves:

$$
t_{CS} = \frac{CAAR}{s_{CAR}/\sqrt{N}},
\qquad
s_{CAR}^2 = \frac{1}{N-1}\sum_{i=1}^N \big(CAR_i - CAAR\big)^2 .
$$

Its strength is that it stays valid when the event itself changes the variance (event-induced variance), and it does not need equal variances across events. Its weakness is that it still assumes the events are independent of each other [17].

### 3.5 Power (Reported: [17])

Suppose ARs have a daily standard deviation of 2% and the window is one day. Then a true AR of 0.5% is detected by a 5% two-sided test only about 20% of the time with 20 firms. You need more than 60 firms to reach 50% power. Large effects are easy to find: a 2% AR with 20 firms gives power of 0.99. Power falls sharply as the window gets longer or the variance gets higher. MacKinlay's own earnings example (600 announcements by 30 Dow firms, 1989–1993) finds day-0 average ARs of +0.965% for good news and −0.679% for bad news.

### 3.6 Brown and Warner (1985): daily data and clustering (Reported: [18], full text)

- Daily data cause few problems. Standard methods are usually well specified, even when non-normality is ignored.
- Allowing for autocorrelation, and for the variance rising around the event, can sometimes help.
- When event dates are spread out, you can ignore cross-sectional dependence, and doing so even gives more power.
- When every event in a sample falls on the same calendar day, things change. With mean-adjusted returns tested as if independent, a true null was rejected 25.2% of the time at a nominal 5% level (one-tailed, 50 securities). The market model, which strips out the common market move, brought that down to 8.0%.

The lesson for us: subtracting the market-wide component (for IV, the VIX or an index IV) removes much of the common shock, but not all of it.

### 3.7 How this project uses it

The project keeps the same skeleton with IV in place of returns (ADR 0004):

- an event window of [−10, +10] sessions;
- a baseline of [−60, −22] that drops sessions near other events;
- a VIX "market model" for log IV, with β estimated for each firm.

It does **not** test a CAAIV. §9 explains why.

---

## 4. Patell (1976): standardised abnormal returns

### 4.1 Idea

Volatile stocks produce large ARs by chance, so if you average raw ARs, those stocks dominate. Patell first divides each AR by its own forecast standard deviation, so that every event counts in units of standard deviations [17], [19].

### 4.2 Maths (Reported: [27], [23]; consistent with [17])

$$
SAR_{i\tau} = \frac{AR_{i\tau}}{s_{i\tau}},
\qquad
s_{i\tau}^2 = s_i^2\left(1 + \frac{1}{L_i} + \frac{(R_{m\tau} - \bar R_m)^2}{\sum_{t\in\text{est}} (R_{mt} - \bar R_m)^2}\right)
$$

- $s_i^2$ is the residual variance from firm $i$'s estimation-window regression. For the market model it is $\frac{1}{L_i - 2}\sum \hat\varepsilon_{it}^2$.
- $L_i$ is the number of estimation-window days for firm $i$.
- The term in brackets is the same correction as MacKinlay's eq. (8), written with sample quantities.

Under the null, with normal errors, $SAR_{i\tau}$ follows a Student-$t$ distribution with $L_i - 2$ degrees of freedom. Its variance is therefore $(L_i-2)/(L_i-4)$, not 1. That gives:

$$
Z_{Patell} = \frac{\sum_{i=1}^N SAR_{i0}}{\sqrt{\sum_{i=1}^N \frac{L_i - 2}{L_i - 4}}} \;\overset{\text{approx}}{\sim}\; N(0,1) .
$$

For a multi-day window, sum standardised CARs instead, for example $SCAR_i = CAR_i/(s_i\sqrt{L_2})$, which drops the small estimation-error terms.

### 4.3 Assumptions and where it breaks

- The events are independent of each other, so there is no clustering.
- The event does not change the variance. If it does, $s_i$ (estimated in a quiet window) is too small and $Z$ is too large. Even a small rise in variance makes the usual tests reject too often [20].
- ARs are serially independent within the window. This is what justifies the $\sqrt{L_2}$.

### 4.4 Use here

Standardising per firm is also useful for IV. A 5-vol-point crush is huge for a utility and routine for a biotech. The standardiser must be estimated from **non-event** IV changes of the same kind: the same maturity rule and the same window length.

---

## 5. Boehmer, Musumeci and Poulsen (1991): the standardised cross-sectional test

### 5.1 Finding (Reported: [20], abstract)

If an event raises variance even slightly, the commonly used tests reject a true null too often. A simple change to the cross-sectional approach fixes this without losing power.

### 5.2 Maths (Reported: [27], [23])

Standardise as Patell does. Then use the cross-sectional spread of the SARs in place of their theoretical variance:

$$
t_{BMP} = \frac{\overline{SAR}_0}{s_{SAR}/\sqrt{N}},
\qquad
\overline{SAR}_0 = \frac{1}{N}\sum_{i=1}^N SAR_{i0},
\qquad
s_{SAR}^2 = \frac{1}{N-1}\sum_{i=1}^N \big(SAR_{i0} - \overline{SAR}_0\big)^2 .
$$

For a window, replace $SAR_{i0}$ with $SCAR_i$. Under the null the statistic is approximately $t$-distributed with $N-1$ degrees of freedom.

Why it works: if the event multiplies every firm's variance by some factor, the event-day SARs spread out more. $s_{SAR}$ picks that up. The Patell denominator does not.

### 5.3 Where it breaks

It still assumes the events are independent. §6 deals with that.

### 5.4 Use here

The crush is, by construction, an event-induced change in variance, and its size varies a lot from firm to firm. The BMP-style cross-sectional variance should therefore be preferred to the Patell-style theoretical variance. ADR 0005 goes further and keeps BMP as a robustness row only. BMP tests the mean of *standardised* effects, a precision-weighted mean. When effects vary with $s_i$, that mean can differ from 0 while the equal-weighted mean the project reports is 0, and BMP then rejects a hypothesis the project did not state (§6.5).

---

## 6. Kolari and Pynnönen (2010): clustering and cross-correlation

### 6.1 Finding (Reported: [21], abstract)

When event dates cluster, even fairly low correlation between firms' abnormal returns makes the standard tests reject far too often. Kolari and Pynnönen modify the BMP statistic to allow for that correlation, and the modified test also works for multi-day CARs. In their comparison, the portfolio approach is less powerful than the alternatives.

Earnings seasons are the textbook case of clustering: hundreds of firms report within a few weeks, many of them on the same day.

### 6.2 Maths

The adjusted statistics below are as given in [27]. The published paper is paywalled and I could not reach a free copy (see "Could not verify").

$$
t_{KP} = t_{BMP}\,\sqrt{\frac{1 - \bar r}{1 + (N-1)\,\bar r}},
\qquad
Z_{Patell,adj} = Z_{Patell}\,\sqrt{\frac{1}{1 + (N-1)\,\bar r}} .
$$

- $\bar r$ is the average pairwise correlation of the (standardised) abnormal returns across the $N$ events, estimated in the estimation window.

**Where the factor comes from (Derived).** Suppose $N$ standardised ARs each have variance 1, and every pair has correlation $\bar r$.

- The variance of their sum is $N + N(N-1)\bar r = N[1 + (N-1)\bar r]$. Patell assumes it is $N$, so dividing by $\sqrt{1+(N-1)\bar r}$ corrects it.
- The expected sample variance *across* the $N$ values is $1 - \bar r$, not 1. A shared shock moves everyone together, so it does not show up as spread. BMP's denominator is therefore too small in two ways: it is short by a factor of $\sqrt{1-\bar r}$, and it misses the $1+(N-1)\bar r$ term. Correcting both gives the BMP factor above.

**Simulation check (my code, not from the paper).** I used 50 events, $\bar r = 0.05$, no true effect and 20,000 repetitions. The unadjusted BMP-type $t$ rejected 31% of the time at a nominal 5%. The adjusted one rejected 5.6% of the time.

**How large is the correction? (Derived)** Multiply the BMP $t$ by:

| $\bar r$ | N = 10 | N = 50 | N = 200 | N = 500 |
|---|---|---|---|---|
| 0.01 | 0.95 | 0.82 | 0.58 | 0.41 |
| 0.05 | 0.81 | 0.53 | 0.30 | 0.19 |
| 0.10 | 0.69 | 0.39 | 0.21 | 0.13 |

With 500 same-day events and $\bar r = 0.05$, a $t$ of 10 shrinks to about 1.9.

### 6.3 Estimating $\bar r$

**Reported [27]:** $\bar r$ is the average pairwise sample correlation of estimation-window abnormal returns.

Two practical points:

- **Derived:** $N$ events give $N(N-1)/2$ pairs. There is a shortcut. Standardise each series to unit variance and take the cross-sectional mean $\bar z_t$ on each day. Then $\operatorname{Var}_t(\bar z_t) \approx [1 + (N-1)\bar r]/N$, so $\bar r \approx \big(N\operatorname{Var}_t(\bar z_t) - 1\big)/(N-1)$. **Reported [39]:** the same identity is published as Pynnönen (2022) eq. 27, $\operatorname{var}(\bar z) = (1+(n-1)\bar\rho)/n$.
- **Derived:** correlations can only be measured over calendar days the series have in common. With full clustering, the estimation windows coincide. With *partial* clustering, where earnings are spread across a season, the windows only partly overlap and the full-clustering factor over-corrects. **Reported [24], [39]:** Kolari, Pape and Pynnönen (2018) [24] address partially overlapping windows. Their abstract says they "adjust for the average percentage of overlaps in event windows"; the full text was not reachable. Pynnönen (2022) [39], read in full, gives the per-pair correlation of two window sums, $(\tau_{ij}/\tau)\rho_{ij}$ with $\tau_{ij}$ the shared days, times a factor specific to ranks (eq. 25), and credits the average-overlap inflation factor $1+(n-1)\nu\bar\rho$, $\nu = \bar\tau/\tau$, to [24].

### 6.4 The 2011 rank test (Reported: [22], [23])

Kolari and Pynnönen (2011) propose a generalised rank test (GRANK). It works for single days and for multi-day CARs, is robust to serial correlation and to event-induced volatility, and in their simulations is more powerful than the Patell and BMP tests. In the 2009 working paper, the CAR window is first collapsed into a single "cumulative event day" by re-standardising the CAR, and that day is then ranked together with the estimation days [23]. This matters here because IV windows are multi-day and serially dependent.

### 6.5 Use here

A VIX move hits every firm's IV on the same day, so IV cross-correlation is probably higher than for returns. **Open: measure it.** Hann, Kim and Zheng [32] also show that industry peers' IV moves with the announcing firm's IV and with the VIX, which adds correlation beyond same-day clustering.

**What ADR 0005 does.** Its primary statistic is not a KP-type statistic but a two-way cluster-robust $t$ (§8): clustered by day-0 date × firm for the one-session crush, and by season × firm for the run-up and persistence, which span about 60 sessions. A KP-type adjustment for a multi-session measure needs a model of the autocorrelation of daily changes, and every estimate of it that the ADR's simulations tried left the statistic mis-sized. The KP family is reported as robustness, for one-session measures only, and labelled as a test of the precision-weighted mean (§5.4): KPP's average-overlap statistic [24] and its per-pair form ([39] eq. 25). The first version of the ADR called the per-pair form its own unpublished generalisation. The milestone-0 review refuted that: it is at most a refinement of [24].

---

## 7. Nonparametric tests

Daily returns, and IV changes around earnings even more so, are skewed and fat-tailed. Rank and sign tests do not assume normality.

### 7.1 Corrado (1989) rank test (Reported: [17], [23], [27])

For each firm, rank its abnormal returns over the combined estimation and event period, which has $T_i$ days. Convert the ranks into uniform scores, $U_{it} = K_{it}/(T_i+1)$, where $K_{it}$ is the rank. Under the null these scores have mean $\tfrac12$. Then:

$$
z_{rank} = \frac{\bar U_0 - \tfrac12}{S_{\bar U}},
\qquad
\bar U_t = \frac{1}{N_t}\sum_i U_{it},
\qquad
S_{\bar U}^2 = \frac{1}{T}\sum_t \big(\bar U_t - \tfrac12\big)^2 .
$$

- $N_t$ is the number of events with data on day $t$, and $T$ is the number of days in the combined period.

The denominator is built from the time series of mean ranks, which absorbs some of the cross-correlation. MacKinlay [17] gives a simplified version (his eqs. 24–25). The weakness is that ranks are awkward to use for multi-day CARs, which is why GRANK exists [22].

### 7.2 Cowan (1992) generalised sign test (Reported: [27], method as described there)

The plain sign test assumes that half of all ARs are positive under the null [17]. That is wrong when the distribution is skewed. Cowan replaces one-half with the fraction of positive ARs in the estimation window:

$$
\hat p = \frac{1}{N}\sum_{i=1}^N \frac{1}{L_i}\sum_{t\in\text{est}} \mathbf{1}[AR_{it} > 0],
\qquad
z_{GS} = \frac{w - N\hat p}{\sqrt{N\hat p(1-\hat p)}} .
$$

- $w$ is the number of events with a positive event-day AR (or CAR).
- $\mathbf{1}[\cdot]$ equals 1 if the condition is true and 0 otherwise.

### 7.3 Use here

The crush is close to one-signed. A generalised sign test on post-event IV changes answers a simple and robust question: is the share of IV declines higher than on ordinary days? Run it alongside the parametric tests. If they disagree, look at the outliers.

---

## 8. Clustered standard errors for the driver regressions

### 8.1 The problem

A driver regression looks like this:

$$
y_e = a + \mathbf{x}_e'\mathbf{b} + u_e
$$

- $e$ is one event: firm $i$ announcing on date $t$.
- $y_e$ is the outcome, for example the crush or $\sigma_E$.
- $\mathbf{x}_e$ holds the drivers, for example $\lvert SUE\rvert$, firm size or pre-event IV.

OLS standard errors assume the $u_e$ are independent. Two things break that:

- **A time effect.** Events on the same date share market-wide shocks, such as a VIX move or a macro release, so their errors are correlated.
- **A firm effect.** One firm's events in different quarters share persistent traits; some firms always crush a lot.

**Reported [28]:** when both the residuals and the regressors are correlated within a cluster, OLS standard errors are too small. The bias grows with the number of observations per cluster.

### 8.2 One-way and two-way clustering

The one-way cluster-robust variance, with clusters $g = 1,\dots,G$, is:

$$
\hat V = (X'X)^{-1}\left(\sum_{g=1}^{G} X_g'\,\hat u_g\,\hat u_g'\,X_g\right)(X'X)^{-1}
$$

- $X_g$ and $\hat u_g$ are the regressor rows and residuals that belong to cluster $g$.

The middle term allows errors within a cluster to be correlated in any way, but assumes clusters are independent of each other.

**Two-way clustering (Reported: [29], [28], [30]).** Compute three one-way matrices, clustering by firm, by date, and by firm-and-date together, then combine them:

$$
\hat V_{2way} = \hat V_{firm} + \hat V_{date} - \hat V_{firm \cap date}
$$

Subtracting the last term removes double counting. When there is only one observation per firm-date cell, that term is the White (heteroskedasticity-robust) matrix [28].

### 8.3 Assumptions and where it breaks

- It needs many clusters in **both** dimensions. The theory requires both counts to grow large [29]. With few clusters the standard errors are biased and $t$-tests reject too often [28], [29].
- In a finite sample, $\hat V_{2way}$ can have negative values on its diagonal [29].
- **Reported [28], working paper:** when one dimension has only a few clusters, two-way clustering gives almost the same answer as clustering on the more numerous dimension alone.
- Date dummies only remove the time effect if it is a fixed additive shift. Otherwise clustering is safer [28].

### 8.4 Use here

ADR 0005 makes **two-way** clustering primary [29], with $t_{\min(G)-1}$ critical values: day-0 date × firm for one-session measures and for the regressions, and season × firm for the run-up and persistence. Firm is the second dimension because a firm's events share its persistent features, which one-way date or season clusters miss. One-way clustering stays as a robustness row. Two alternatives were tested and rejected. ISO-week clusters for multi-session measures over-rejected badly in the ADR's simulations, because 60-session ramps overlap across many weeks. A wild cluster bootstrap by season (Webb weights) was deleted, because it rejected more often than the plain cluster-robust $t$. The season dimension has only about 7 clusters, the few-cluster case of §8.3. So when seasons are unbalanced the ADR uses a Rademacher randomisation p-value by season instead. Before trusting two-way standard errors, count the distinct dates, seasons and firms in the sample.

For comparison, Augustin, Brenner and Subrahmanyam [31] cluster by date because events bunch on the same days. Hann, Kim and Zheng [32] cluster by industry and report that the results survive clustering by industry and quarter.

---

## 9. Applying return-based tests to implied volatility

This is the most important section. The tools above assume that abnormal returns are roughly independent over time, roughly zero on average outside events, and comparable across firms. IV breaks all three assumptions.

### 9.1 How IV differs from a return

1. **IV levels are persistent.** The VIX has long memory, and a simple HAR model is hard to beat at forecasting it [33]. I found no source that measures how persistent single-stock IV is. **Open: estimate the AR(1) coefficient of daily ATM IV for each firm.**
2. **IV moves predictably around the event.** For a fixed expiry, the model in §1 makes IV drift upward like $1/T$ before the event. So the "normal" IV change in the pre-event window is not zero, and a benchmark estimated from quiet periods will label that run-up abnormal. That may be exactly what you want, but say so explicitly.
3. **Constant-maturity IV mixes effects.** An interpolated 30-day IV only contains the event once the event is within 30 days, and the event's weight changes as the days pass. Hann, Kim and Zheng find weaker results for 30-day standardised options than for longer ones [32]. Donders and Vorst always used the shortest expiry with at least 10 days left [6], so the series switches expiry within the window.
4. **The size of the crush depends on maturity.** In variance units it is $\sigma_E^2/T$. Vol-point changes cannot be compared across expiries, but total-variance changes can.
5. **Moneyness drift.** After a 10% jump, yesterday's ATM strike is far from the money. With a skew, "ATM IV" then changes for reasons unrelated to uncertainty. Using constant-delta or constant-moneyness IV avoids this.
6. **Quote noise.** IV computed from bid–ask midpoints is noisy. Noise that is independent from day to day makes daily IV changes negatively autocorrelated.
7. **Common shocks.** A VIX move hits every option at once, and industry peers' IV moves together with the announcing firm's [32].

### 9.2 What goes wrong with the return formulas (Derived)

- **A "CAR" of IV changes is just a level change.** $\sum_{\tau=\tau_1}^{\tau_2}\Delta IV_\tau = IV_{\tau_2} - IV_{\tau_1-1}$. Summing daily changes is fine. But when changes are autocorrelated, the variance of the sum is not $L_2\,\sigma^2_{\Delta}$.
- **Summing abnormal IV *levels* is wrong.** Neighbouring levels are almost the same number, so their sum has variance close to $L_2^2\sigma^2$, not $L_2\sigma^2$.
- **Simulation (mine, illustrative only).** IV is 40% plus an AR(1) process with $\phi = 0.98$ and daily shocks of 1 vol point, plus 0.5 vol points of quote noise. The estimation window is 120 days and the event window 11 days. There is **no event effect**. I ran 5,000 repetitions of a Patell-style test on each event, with variance equal to $L_2$ times the estimation-window variance.

  | Abnormal IV defined as | False-positive rate at a nominal 5% |
  |---|---|
  | Level minus estimation-window mean, summed over 11 days | 67.5% |
  | Daily change minus estimation-window mean change, summed | 2.2% |

  Levels reject far too often. Changes reject slightly too rarely here, because the quote noise gives daily changes a lag-1 autocorrelation of about −0.17, and that noise cancels out in the sum. These numbers depend entirely on the parameters I assumed. They show which way the problem points, not how big it is in real data.
- **The cross-sectional fix.** A BMP-style or plain cross-sectional test uses the spread of the per-event window statistics instead of $L_2\sigma^2$. That avoids the problem of autocorrelation within the window. It does **not** fix correlation between events (§6, §8).
- **Contaminated baselines.** Earnings come round roughly every 63 trading days, so a 120-day estimation window contains the previous earnings event unless you cut it out.

### 9.3 How published papers defined abnormal IV

| Paper | IV measure | "Normal" benchmark | Inference |
|---|---|---|---|
| Donders and Vorst (1996) [6], full text | Call IV from the shortest expiry with at least 10 days left, nearest the money | Excess IV is IV minus its mean over a control period (all days outside the pre-event, event and post-event windows). Market correction either subtracts the same-maturity index-option IV or uses matched control stocks. | Excess IV regressed on pre/event/post dummies by GMM with Newey–West standard errors. They note that the events cluster in time. |
| Dubinsky and Johannes [3], working paper | ATM IV from the nearest expiries | None: the model supplies the expected path | Estimates $\sigma_E^2$ in total-variance units and checks standardised moves |
| Augustin, Brenner and Subrahmanyam [31], 2014 WP (M&A, not earnings) | OptionMetrics interpolated 30-day IV at 50, 80 and 20 delta | A constant-mean model, or a "market model" using the VIX. Estimation window −90 to −31, event window −30 to −1. | Standard errors clustered by date because of event bunching. From the parts I read, I could not tell whether the VIX model is in levels or in changes. |
| Hann, Kim and Zheng (2019) [32], accepted version | OptionMetrics standardised ATM IV, 30 to 365 days | $\Delta IV = \ln(IV_{+3}/IV_{-3})$, with $\Delta VIX$ as a regression control. The mean $\Delta IV$ for announcers is −0.106 at 30 days. | Standard errors clustered by industry; results robust to clustering by industry and quarter |
| Truong, Corrado and Chen (2012) [16], abstract only | IV changes | Not seen | 3-day post-announcement IV change regressed on earnings news |
| Rogers, Skinner and Van Buskirk (2009) [14], abstract only | IV from exchange-traded options | Not seen | IV changes around forecasts and announcements |
| Neururer et al. (2016) [15], abstract only | Model-free IV | Not seen | IV change against a consensus-based surprise |

### 9.4 What I could not find

- A Brown–Warner-style simulation that tests the size and power of event-study statistics **on IV**.
- A paper that derives Patell- or BMP-type variances for IV while modelling its autocorrelation.
- Estimates of how persistent single-stock IV is.
- An agreed definition of "abnormal IV". The literature variously uses levels minus a mean, log changes, total-variance changes and VIX-adjusted versions of these.

### 9.5 What the project decided, and what is still open

The project's ADRs take the line this section argues for.

- **No CAAIV test** (ADR 0004 §3). Summing levels double-counts, and summed changes collapse to a difference of two levels. So the project tests those levels and changes directly: RUNUP ($\text{ALIV}_{-1}$), CRUSH (the market-adjusted one-session change in log IV at day 0), PERSIST at +1, +5 and +10, $E$, and the change in ordinary volatility.
- **Measure** (ADR 0004 §2): log 30-day IV, adjusted by a VIX "market model" with a β for each firm, which is closest to [31] and [32]. The mean-adjusted version is reported alongside. The baseline excludes the zones around other events.
- **Tests** (ADR 0005): each tested quantity is written as a weighted sum of one-session changes. The primary test is a two-way cluster-robust $t$ on the equal-weighted mean (day-0 date × firm for the crush, season × firm for the run-up and persistence), which needs no autocorrelation model. BMP, the KP family with KPP's overlap adjustment, one-way clustered $t$, a Rademacher p-value by season, Patell, and generalised sign and rank tests are robustness. A size gate at the real design (G1) must pass before any H1–H4 p-value is reported.
- **Placebo** (ADR 0004): the mean-adjusted pipeline is run on SPY's chain at the real day-0 dates. This is Brown and Warner's logic [18] applied to IV.

Still open:

- How persistent single-stock IV is, and what the actual β of $\Delta\ln IV$ on $\Delta\ln VIX$ is.
- Whether the two-way primary passes the size gate G1 on the real event set at milestone 3 (ADR 0005 §5).
- *Resolved:* whether the overlap-weighted KP was the project's own. It is not: it is at most a refinement of [24], and [39] gives the per-pair weight.

---

## 10. Measuring the earnings surprise

### 10.1 Time-series SUE

The seasonal random walk uses the same quarter of last year as the forecast:

$$
UE_{iq} = EPS_{iq} - EPS_{i,q-4},
\qquad
SUE_{iq} = \frac{UE_{iq}}{\text{scale}_{iq}}
$$

- $EPS_{iq}$ is earnings per share of firm $i$ in quarter $q$, and $q-4$ is the same quarter a year earlier.
- There are two choices of scale:
  - the standard deviation of $UE$ over earlier quarters. This is the classic "standardised" version associated with Foster, Olsen and Shevlin [34] and Bernard and Thomas [35]. I have not read their exact window or whether they include a drift term.
  - the share price. These are Livnat and Mendenhall's SUE1 and SUE2, as described in [37].

### 10.2 Analyst-consensus surprise

$$
SUE^{A}_{iq} = \frac{A_{iq} - F_{iq}}{P_{iq}}
\quad\text{or}\quad
\frac{A_{iq} - F_{iq}}{\sigma_{F,iq}}
$$

- $A$ is actual EPS, measured on the same basis as the forecasts (for example, I/B/E/S actuals).
- $F$ is the consensus forecast just before the announcement.
- $P$ is the share price.
- $\sigma_F$ is the standard deviation of analysts' forecasts, also called dispersion.

**Reported:** post-announcement drift is significantly larger when surprises are measured against analyst forecasts than against a time-series model [36]. Their analyst measure (SUE3) is scaled by price, according to [37].

### 10.3 The tiny-denominator problem (Derived, except Cheong and Thomas)

- When there is one analyst, or all analysts agree, $\sigma_F$ is close to zero, and the ratio explodes on trivial misses.
- Near break-even, $\lvert F\rvert$ is close to zero, so percentage surprises explode and can flip sign.
- Low share prices inflate price-scaled surprises.
- **Reported [38]:** analysts' EPS forecast errors and dispersion do not vary with scale (for firms that analysts follow). The authors attribute this to firms smoothing EPS. I did not read how they define scale. If scale includes price, then price-scaled surprises will be mechanically larger for low-priced stocks.

**Guardrails:**

- Require a minimum number of analysts before scaling by dispersion.
- Put a floor under the denominator.
- Winsorise; both [37] and [32] winsorise at the 1st and 99th percentiles.
- Run a rank or decile version of SUE as a robustness check.

### 10.4 Use here

In ADR 0005, the primary driver is the price-scaled absolute surprise $\lvert\text{reported} - \text{estimate}\rvert / P_{-1}$, winsorised. Three other forms are robustness checks:

- a historical SUE;
- a surprise scaled by the high–low range of estimates, when there are at least 3;
- the signed surprise.

The ADR rejects percentage surprises because they explode near zero EPS, which is the tiny-denominator problem in §10.3.

The IV literature says the surprise acts in a non-linear and asymmetric way:

- IV falls less after bigger surprises, and can rise after very large ones [15].
- IV changes respond more strongly to bad news [16].
- Bad news can leave IV flat or push it higher [7].

So a specification that uses $\lvert SURP\rvert$ alone may miss the asymmetry. **Open:** check the signed and non-linear variants before concluding that the surprise does not matter.

---

## Glossary

- **IV (implied volatility).** The volatility that, plugged into an option-pricing model (usually Black–Scholes), reproduces the option's market price. It is annualised. It is a price, not a forecast, so it contains risk premia.
- **ATM (at the money).** The strike equal or nearest to the current price or forward. Common versions are the nearest strike, the 50-delta option, or moneyness $K/S = 1$.
- **Term structure.** IV plotted against time to expiry at fixed moneyness. Before earnings it usually slopes down.
- **Total variance.** $w = \sigma^2 T$. It adds up across non-overlapping stretches of time, which makes it the right unit for comparing expiries.
- **Event variance ($\sigma_E^2$).** The extra variance of the log price caused by the announcement. It is not annualised.
- **Implied move.** In this project, $\sigma_E$, or the expected absolute move $\approx 0.80\,\sigma_E$. Traders' version is the straddle price divided by spot, which also includes ordinary variance.
- **Crush.** The fall in IV once the event has passed. For the front expiry it is about $\sigma_E^2/T$ in variance units.
- **AR, AAR, CAR, CAAR.** Abnormal return; its average across events; its sum over a window; and the cross-event average of that sum.
- **SAR.** A standardised abnormal return: the AR divided by its forecast standard deviation (Patell).
- **AIV (abnormal implied volatility).** IV minus a "normal" benchmark. In ADR 0004, $\text{AIV}_t$ is the 30-day IV minus its baseline mean, in vol points, and is used for display only. The tested version is $\text{ALIV}_t$: log IV minus its baseline mean, adjusted for VIX.
- **CAAIV.** Cumulative average abnormal IV: the cross-event average of each event's AIV, accumulated over a window. It is the IV analogue of CAAR. Summing levels double-counts, and summing changes collapses to a level difference, so this project plots the mean abnormal path but does not test a CAAIV (ADR 0004 §3, §9.2 here).
- **BMP.** The Boehmer–Musumeci–Poulsen (1991) standardised cross-sectional test.
- **KP.** Kolari and Pynnönen's (2010) adjustment of BMP, and of Patell, for cross-correlation caused by clustered event dates.
- **$\bar r$.** The average pairwise correlation of abnormal series across events, used in KP.
- **SUE.** Standardised unexpected earnings: the earnings surprise divided by a scale, which can be the standard deviation of past surprises, the share price, or analyst dispersion.
- **BMO/AMC.** Before market open / after market close. A BMO announcement on day $d$ moves the price on day $d$. An AMC announcement on day $d$ moves it on day $d+1$.
- **Q versus P.** The risk-neutral (option-implied) probability measure versus the real-world one. $\sigma_E$ from options is a Q quantity.

---

## How this project uses each idea

| Idea | Source | Where the project uses it |
|---|---|---|
| Scheduled jump; total variance $w = \sigma^2T$ | [1]–[4], [6] | ADR 0003 §0: the stored building block is ATM $w$ per expiry |
| Two-expiry estimator of event variance | [3] | ADR 0003 (c): $E$ at day −1, stored with its sign, averaged in variance space |
| Implied move | §1.4, [3] | ADR 0003 (c): $\sqrt E$; $\sqrt{2/\pi}\sqrt{E+\sigma_d^2/252}$ compared with $\lvert r_0\rvert$; straddle used only as a cross-check |
| Day-count clock | [3], §1.5 | ADR 0003: NYSE sessions |
| Risk-neutral versus realised | [3], [9], [11], [12] | ADR 0005 H7: $r_0^2 = a + b\,(E + \sigma_d^2/252)$ with $\sigma_d$ annualised; test $a=0$, $b=1$; a description, not a trading claim |
| BMO/AMC alignment | [3], [11], [37] | ADR 0002: day 0 is the first session whose close reflects the news |
| Estimation and event windows | [17], [18] | ADR 0004 §1: [−10, +10]; baseline [−60, −22] with other events' zones removed |
| Market-model analogue for IV | [6], [18], [31], [32] | ADR 0004 §2: log IV adjusted with VIX using each firm's β; mean-adjusted as a robustness check |
| CAAIV versus testing levels and changes | [17], §9.2 | ADR 0004 §3: no CAAIV test; RUNUP, CRUSH and PERSIST tested directly |
| Patell standardisation | [19] | ADR 0005: standardise by baseline scale; Patell itself reported for CRUSH only |
| BMP | [20] | ADR 0005: robustness, labelled as a test of the precision-weighted mean; the base of the KP rows |
| KP adjustment | [21], [24], [39] | ADR 0005: robustness for one-session measures: KPP's average-overlap statistic [24] and its per-pair form ([39] eq. 25); the KP (2010) all-pairs row was deleted |
| Rank and sign tests | [22], [25], [26] | ADR 0005: generalised sign and rank tests as companions |
| Clustered standard errors | [28]–[30] | ADR 0005: the primary test. Two-way date × firm for one-session measures and regressions, season × firm for run-up and persistence; one-way as robustness; ISO-week clusters rejected |
| Placebo | [18] | ADR 0004: SPY chain at the real day-0 dates; ADR 0005: Monte Carlo size checks |
| SUE | [34]–[38] | ADR 0005: price-scaled $\lvert SURP\rvert$ as primary; historical, range-scaled and signed versions as robustness |

---

## Open questions for this project

The ADRs settle the design. These questions can only be answered by the data, or by reading the sources I could not reach:

1. How persistent is daily single-stock IV in our data, and how negative is the lag-1 autocorrelation of daily changes? (§9.1)
2. How large is $\bar r$ within an earnings season, and what is the β of $\Delta\ln IV$ on $\Delta\ln VIX$? (§6.5, §9.5)
3. *Resolved.* Does ADR 0005's overlap-weighted KP agree with Kolari, Pape and Pynnönen (2018) [24] and Pynnönen (2022) [39]? Yes: it is at most a refinement of [24], and [39] gives the per-pair weight. It is now a robustness row; the primary is a two-way clustered $t$ (§6.3, §6.5, §8.4).
4. Does the realised move fall short of $E$ (as in [3]) or exceed it (as [11] implies), and does that differ by firm size? (§2.2)
5. Does the crush respond asymmetrically to the sign of the surprise, as [7], [15] and [16] report? (§10.4)
6. What share of events have $E \le 0$? A high share means the flat ex-event term structure assumption is failing. (§1.6)

---

## Could not verify

- **Kolari and Pynnönen (2010) [21]:** the exact published formula, and their exact estimator for $\bar r$. The RFS full text is paywalled, and the free copies on CORE, SSRN and the University of Vaasa repository were blocked by bot protection. The formula above comes from a secondary source [27], my own derivation, and a Monte Carlo check.
- **Patell (1976) [19], Boehmer, Musumeci and Poulsen (1991) [20], Corrado (1989) [25], Cowan (1992) [26]:** I did not read the originals. I confirmed each citation through its DOI and read BMP's abstract. The formulas come from MacKinlay [17], Kolari and Pynnönen's 2009 working paper [23] and EventStudyTools [27]. Bibliographic databases spell BMP's second author "Masumeci"; MacKinlay spells it "Musumeci", which I use here.
- **Patell and Wolfson (1981) [2]:** I read neither the text nor the abstract. It is described here only as later papers describe it.
- **Dubinsky, Johannes, Kaeck and Seeger (2019) [4]:** I read only the abstract and the 2017 slides. I did not check whether the published estimators differ from the 2004 working paper's.
- **The Intel ex-post estimate:** *resolved.* The printed inputs give 8.0% with $T = 5/252$; [3]'s 7.2% is reproduced with $T = 4/252$ (§1.3).
- **Foster, Olsen and Shevlin (1984) [34] and Bernard and Thomas (1989) [35]:** I did not read the exact SUE definitions (scale, window, drift). The Livnat and Mendenhall definitions come from a secondary source [37].
- **Billings and Jennings (2011) [13] and Barth and So (2014) [12]:** I read the abstracts only and did not see how they build their measures.
- **Augustin, Brenner and Subrahmanyam [31]:** I read only the 2014 working paper. The published 2019 method may differ, and I could not tell whether the VIX model is in levels or in changes.
- **Brenner and Subrahmanyam (1988) [10]:** I confirmed the citation only. The straddle approximation in §1.4 is my own derivation.
- **Kolari, Pape and Pynnönen (2018) [24]:** abstract read (through Crossref); the full text was not reachable (SSRN returned 403), so their exact parametric statistic is known only as Pynnönen (2022) [39] describes it. [39] was read in full for ADR 0005 on 2026-10-28.
- **The title of the Dubinsky and Johannes working paper:** the Columbia PDF I read (`DJ_2006.pdf`) is titled *Earnings announcements and equity options* and dated September 2004. ADR 0003 cites a 2006 version titled *Fundamental uncertainty, earning announcements and equity options*. A ResearchGate listing uses that title, but I did not open that version.
- **Persistence of single-stock IV, and size and power simulations for event-study tests on IV:** no source found.

---

## References

For each source, "Read" says how much of it I actually saw. Every DOI was resolved through Crossref on 2026-10-28.

1. Patell, J. M., & Wolfson, M. A. (1979). Anticipated information releases reflected in call option prices. *Journal of Accounting and Economics*, 1(2), 117–140. https://doi.org/10.1016/0165-4101(79)90003-X. Read: the Stanford GSB summary page.
2. Patell, J. M., & Wolfson, M. A. (1981). The ex ante and ex post price effects of quarterly earnings announcements reflected in option and stock prices. *Journal of Accounting Research*, 19(2), from p. 434. https://doi.org/10.2307/2490874. Read: bibliographic record only.
3. Dubinsky, A., & Johannes, M. *Earnings announcements and equity options*. Working paper, Columbia Business School; draft of September 2004 (first draft November 2003), hosted as `DJ_2006.pdf`. https://business.columbia.edu/sites/default/files-efs/pubfiles/6051/DJ_2006.pdf. Read: introduction, model, estimator and risk-premium sections.
4. Dubinsky, A., Johannes, M., Kaeck, A., & Seeger, N. J. (2019). Option pricing of earnings announcement risks. *Review of Financial Studies*, 32(2), 646–687. https://doi.org/10.1093/rfs/hhy060. Read: abstract.
5. Dubinsky, A., Johannes, M., Kaeck, A., & Seeger, N. (2017). *Option pricing of earnings announcement risks*. Slides, Derivatives and Volatility Conference, NYU Stern. https://www.stern.nyu.edu/sites/default/files/assets/documents/NYU%20conference%20Johannes%20final.pdf. Read: full slides.
6. Donders, M. W. M., & Vorst, T. C. F. (1996). The impact of firm specific news on implied volatilities. *Journal of Banking & Finance*, 20(9), 1447–1461. https://doi.org/10.1016/S0378-4266(96)00011-8. Read: full text (Erasmus repository).
7. Isakov, D., & Pérignon, C. (2001). Evolution of market uncertainty around earnings announcements. *Journal of Banking & Finance*, 25(9), 1769–1788. https://doi.org/10.1016/S0378-4266(00)00158-8. Read: working-paper abstract (IDEAS).
8. Ederington, L. H., & Lee, J. H. (1996). The creation and resolution of market uncertainty: The impact of information releases on implied volatility. *Journal of Financial and Quantitative Analysis*, 31(4), 513–539. https://doi.org/10.2307/2331358. Read: abstract (IDEAS).
9. Alexiou, L., Goyal, A., Kostakis, A., & Rompolis, L. (2025). Pricing event risk: Evidence from concave implied volatility curves. *Review of Finance*, 29(4), 963–1007. https://doi.org/10.1093/rof/rfaf016. Read: abstract.
10. Brenner, M., & Subrahmanyam, M. G. (1988). A simple formula to compute the implied standard deviation. *Financial Analysts Journal*, 44(5), 80–83. https://doi.org/10.2469/faj.v44.n5.80. Read: bibliographic record only.
11. Gao, C., Xing, Y., & Zhang, X. (2018). Anticipating uncertainty: Straddles around earnings announcements. *Journal of Financial and Quantitative Analysis*, 53(6), 2587–2617. https://doi.org/10.1017/S0022109018000285. Read: abstract, plus parts of the November 2017 working paper (data, timing and straddle construction).
12. Barth, M. E., & So, E. C. (2014). Non-diversifiable volatility risk and risk premiums at earnings announcements. *The Accounting Review*, 89(5), 1579–1607. https://doi.org/10.2308/accr-50758. Read: abstract (MIT DSpace).
13. Billings, M. B., & Jennings, R. (2011). The option market's anticipation of information content in earnings announcements. *Review of Accounting Studies*, 16(3), 587–619. https://doi.org/10.1007/s11142-011-9156-5. Read: abstract.
14. Rogers, J. L., Skinner, D. J., & Van Buskirk, A. (2009). Earnings guidance and market uncertainty. *Journal of Accounting and Economics*, 48(1), 90–109. https://doi.org/10.1016/j.jacceco.2009.07.001. Read: abstract.
15. Neururer, T., Papadakis, G., & Riedl, E. J. (2016). Tests of investor learning models using earnings innovations and implied volatilities. *Review of Accounting Studies*, 21(2), 400–437. https://doi.org/10.1007/s11142-015-9348-5. Read: abstract.
16. Truong, C., Corrado, C., & Chen, Y. (2012). The options market response to accounting earnings announcements. *Journal of International Financial Markets, Institutions and Money*, 22(3), 423–450. https://doi.org/10.1016/j.intfin.2012.01.006. Read: abstract.
17. MacKinlay, A. C. (1997). Event studies in economics and finance. *Journal of Economic Literature*, 35(1), 13–39. https://ideas.repec.org/a/aea/jeclit/v35y1997i1p13-39.html (no DOI). Read: JSTOR scan, pp. 19–33.
18. Brown, S. J., & Warner, J. B. (1985). Using daily stock returns: The case of event studies. *Journal of Financial Economics*, 14(1), 3–31. https://doi.org/10.1016/0304-405X(85)90042-X. Read: full text.
19. Patell, J. M. (1976). Corporate forecasts of earnings per share and stock price behavior: Empirical test. *Journal of Accounting Research*, 14(2), 246–276. https://doi.org/10.2307/2490543. Read: bibliographic record only.
20. Boehmer, E., Musumeci, J., & Poulsen, A. B. (1991). Event-study methodology under conditions of event-induced variance. *Journal of Financial Economics*, 30(2), 253–272. https://doi.org/10.1016/0304-405X(91)90032-F. Read: abstract (Semantic Scholar).
21. Kolari, J. W., & Pynnönen, S. (2010). Event study testing with cross-sectional correlation of abnormal returns. *Review of Financial Studies*, 23(11), 3996–4025. https://doi.org/10.1093/rfs/hhq072. Read: abstract (IDEAS).
22. Kolari, J. W., & Pynnönen, S. (2011). Nonparametric rank tests for event studies. *Journal of Empirical Finance*, 18(5), 953–971. https://doi.org/10.1016/j.jempfin.2011.08.003. Read: abstract (EconPapers).
23. Kolari, J. W., & Pynnönen, S. (2009). *Generalized rank test for testing cumulative abnormal returns in event studies*. EFMA 2009 conference paper. https://efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2009-Milan/papers/137.pdf. Read: test-statistic and GSAR sections.
24. Kolari, J. W., Pape, B., & Pynnönen, S. (2018). *Event study testing with cross-sectional correlation due to partially overlapping event windows*. SSRN working paper. https://doi.org/10.2139/ssrn.3167271. Read: abstract (Crossref); full text not reachable (SSRN returned 403).
25. Corrado, C. J. (1989). A nonparametric test for abnormal security-price performance in event studies. *Journal of Financial Economics*, 23(2), 385–395. https://doi.org/10.1016/0304-405X(89)90064-0. Read: bibliographic record only.
26. Cowan, A. R. (1992). Nonparametric event study tests. *Review of Quantitative Finance and Accounting*, 2(4), 343–358. https://doi.org/10.1007/BF00939016. Read: bibliographic record only.
27. EventStudyTools. *Significance tests* (methodology page). https://www.eventstudytools.com/methodology/test-statistics. Accessed 2026-10-28. Secondary source.
28. Petersen, M. A. (2009). Estimating standard errors in finance panel data sets: Comparing approaches. *Review of Financial Studies*, 22(1), 435–480. https://doi.org/10.1093/rfs/hhn053. Read: abstract, plus NBER Working Paper 11280 (2005, revised 2006), https://www.nber.org/papers/w11280.
29. Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2011). Robust inference with multiway clustering. *Journal of Business & Economic Statistics*, 29(2), 238–249. https://doi.org/10.1198/jbes.2010.07136. Read: NBER Technical Working Paper 327 (2006), https://www.nber.org/papers/t0327.
30. Thompson, S. B. (2011). Simple formulas for standard errors that cluster by both firm and time. *Journal of Financial Economics*, 99(1), 1–10. https://doi.org/10.1016/j.jfineco.2010.08.016. Read: bibliographic record only (cited by [28] and [29]).
31. Augustin, P., Brenner, M., & Subrahmanyam, M. G. (2019). Informed options trading prior to takeover announcements: Insider trading? *Management Science*, 65(12), 5697–5720. https://doi.org/10.1287/mnsc.2018.3122. Read: abstract, plus the May 2014 working paper (https://doi.org/10.2139/ssrn.2441606), excess-IV section.
32. Hann, R. N., Kim, H., & Zheng, Y. (2019). Intra-industry information transfers: Evidence from changes in implied volatility around earnings announcements. *Review of Accounting Studies*, 24(3), 927–971. https://doi.org/10.1007/s11142-019-9487-1. Read: October 2018 accepted version, https://care-mendoza.nd.edu/assets/293764/hann_kim_zheng_rast_oct2018.pdf.
33. Fernandes, M., Medeiros, M. C., & Scharth, M. (2014). Modeling and predicting the CBOE market volatility index. *Journal of Banking & Finance*, 40, 1–10. https://doi.org/10.1016/j.jbankfin.2013.11.004. Read: abstract.
34. Foster, G., Olsen, C., & Shevlin, T. (1984). Earnings releases, anomalies, and the behavior of security returns. *The Accounting Review*, 59(4), 574–603. https://doi.org/10.2308/tar-4483133. Read: bibliographic record only.
35. Bernard, V. L., & Thomas, J. K. (1989). Post-earnings-announcement drift: Delayed price response or risk premium? *Journal of Accounting Research*, 27 (Supplement), from p. 1. https://doi.org/10.2307/2491062. Read: bibliographic record only.
36. Livnat, J., & Mendenhall, R. R. (2006). Comparing the post-earnings announcement drift for surprises calculated from analyst and time series forecasts. *Journal of Accounting Research*, 44(1), 177–205. https://doi.org/10.1111/j.1475-679X.2006.00196.x. Read: abstract.
37. Meursault, V., Liang, P. J., Routledge, B. R., & Scanlon, M. M. (2023). PEAD.txt: Post-earnings-announcement drift using text. *Journal of Financial and Quantitative Analysis*, 58(6), 2299–2326. https://doi.org/10.1017/S0022109022001181. Read: online appendix (SUE construction and announcement timing).
38. Cheong, F. S., & Thomas, J. (2011). Why do EPS forecast error and dispersion not vary with scale? Implications for analyst and managerial behavior. *Journal of Accounting Research*, 49(2), 359–401. https://doi.org/10.1111/j.1475-679X.2010.00387.x. Read: abstract.
39. Pynnönen, S. (2022). Non-Parametric Statistic for Testing Cumulative Abnormal Stock Returns. *Journal of Risk and Financial Management*, 15(4), 149. https://doi.org/10.3390/jrfm15040149 (CC BY 4.0). Read: full text. Very likely the published version of the SSRN working paper *Nonparametric rank tests in event studies with partially overlapping event windows* (2021), https://doi.org/10.2139/ssrn.3802405: same author and a nearly identical abstract, but the article does not cite it, so the link is inferred.
