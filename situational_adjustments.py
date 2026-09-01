# Manual overrides for real offseason context (depth-chart changes,
# coaching changes, scheme shifts) that a purely historical-stats model
# has no way to see. It only knows what already happened on the field,
# not roster moves affecting the season ahead. Like suspensions.py, this
# needs to be updated by hand as real news breaks. This is inherently a
# judgment call, not something derived from data.
#
# Each entry is a multiplier on projected_ppg: >1.0 = increased
# opportunity (a committee-mate left, more competition), <1.0 = decreased
# opportunity (new competition arrived, scheme deemphasizes them).
SITUATIONAL_ADJUSTMENTS = {
    # Lions traded David Montgomery (36% of the backfield's touches in
    # 2025: 187 touches, 166.9 pts) to Houston in the 2026 offseason. HC
    # Dan Campbell has explicitly named Gibbs the bell-cow back for 2026.
    # Gibbs already held 63.6% of team RB touches in 2025 and was more
    # efficient per touch than Montgomery (1.09 vs 0.89 pts/touch). A
    # conservative estimate has him absorbing a large share of the
    # vacated work. This number is a judgment call based on real news,
    # not a calculation -- revisit if Detroit adds a real committee back
    # during the season.
    'Jahmyr Gibbs': 1.25,

    # McCaffrey no longer needs an override here: his original problem was
    # the age/durability curve over-penalizing a 2025 injury-shortened
    # season despite no real decline in ability. The age_adjustment
    # module's recent-trend check now handles exactly this automatically
    # (his own data shows no decline, so his age discount is already fully
    # negated) -- keeping this override too was double-counting the same
    # fix and pushed him to an unrealistic #2 overall.

    # Jefferson's elite 2025 volume (141 targets, 8.3/game) is already
    # credited by the automatic target-share signal -- what that signal
    # can't see is that only 2 of those targets became TDs all season,
    # dragging his points down despite the volume. That's an efficiency
    # problem tied to historically bad Vikings QB play (McCarthy hurt and
    # inaccurate, plus Wentz/Brosmer), which Minnesota addressed by
    # bringing in Kyler Murray. This is now sized to just the TD-rate/
    # efficiency recovery, not the volume (already counted automatically).
    'Justin Jefferson': 1.08,

    # Rams RB2 Blake Corum is genuinely pushing for more work -- last
    # season's 60/40 split (Williams/Corum) could become the most shared
    # backfield of the McVay era per multiple 2026 offseason reports.
    # Williams still holds clear priority in big moments, so this is a
    # moderate discount, not a committee-back-level one.
    'Kyren Williams': 0.85,

    # Irving's real committee risk (efficiency collapse, offseason shoulder
    # surgery, new competition from Kenneth Gainwell) is now handled by the
    # automatic backup_threat signal instead of a hand-guessed multiplier
    # here -- that signal turned out to be much better calibrated (it
    # measures Gainwell's actual 2025 usage/efficiency directly) than our
    # original estimate, and stacking both was a significant overcorrection.

    # Hall's own talent isn't in question, but a genuinely weak Jets
    # offense has suppressed his production for multiple years with no
    # clear sign of reversing -- a team-context drag, not a role concern.
    'Breece Hall': 0.90,

    # Smith's current elite share (~25%, while still splitting with Brown)
    # is already credited by the automatic target-share signal. This is
    # now sized to just the *further* increase real analysts expect on top
    # of that -- toward ~30% -- now that Brown is traded to New England,
    # not the share he already gets credit for.
    'DeVonta Smith': 1.05,

    # McConkey's 2025 target share was itself suppressed by Keenan Allen
    # eating into his role, so the automatic signal already reflects a
    # down year, not his true talent level. This is now sized to the
    # incremental recovery expected now that Allen has departed and LA
    # hired Mike McDaniel (known for scheme creativity) as OC -- not the
    # full swing back to his 2024 level, since some of that is already
    # implicit in a healthier target share going forward.
    'Ladd McConkey': 1.08,

    # Kittle tore his Achilles in the January 2026 playoffs -- after our
    # entire 2023-2025 data window ends, so no amount of historical
    # analysis could ever see it. Entering his age-33 season off a serious
    # injury with real recovery-timeline uncertainty, real analysts
    # describe him as a "risk/reward low-end TE1," not a clear top-of-tier
    # option despite his still-strong trailing production.
    'George Kittle': 0.75,

    # Mixon missed the entire 2025 season with a serious foot injury
    # (blood-flow issues, multiple surgeries) -- invisible to our model
    # since a missing season just silently drops out of the data window
    # rather than flagging anything. He was released by Houston in March
    # 2026 and is currently not on any NFL roster; real reports describe
    # his career as "likely over." Our model was ranking him #11 purely
    # off his strong 2023-2024 numbers with no idea any of this happened.
    'Joe Mixon': 0.15,

    # Aiyuk tore his ACL/MCL in Week 7, 2024 and hasn't played an NFL game
    # since -- 600+ days. He was placed on the Reserve/Left Squad list amid
    # a contract dispute (going AWOL from the team) and is currently
    # ineligible to play in the NFL at all unless he petitions the
    # Commissioner for reinstatement. The 49ers GM said in January 2026
    # "it's safe to say he's played his last snap" with the team. Our
    # model was ranking him #38 purely off his strong 2023-2024 numbers.
    'Brandon Aiyuk': 0.05,

    # Moss fractured his C6 vertebra in three places during the 2024
    # season -- a broken neck. Released by Cincinnati in July 2025, he
    # never progressed enough to play at all that season (opened camp on
    # the non-football injury list) and remains unsigned with no clear
    # 2026 outlook. Chase Brown has fully taken over as Cincinnati's lead
    # back. Our model was ranking him purely off his pre-injury numbers.
    'Zack Moss': 0.10,

    # Waddle was traded to Denver in the 2026 offseason -- a brand new team
    # our historical, team-based data has zero visibility into. Real
    # analysts explicitly cite "renewed upside" from the opportunity
    # change (SI has him as high as WR17), even with real durability
    # concerns (missed time each of the last two seasons) tempering it.
    'Jaylen Waddle': 1.12,

    # McLaurin's 2025 decline (11.42 ppg vs 15.75 in 2024, plus missing 7
    # games) was driven by his rookie QB Jayden Daniels' own injury
    # suppressing the whole offense, not a decline in McLaurin's own role
    # -- a recovery story if both stay healthy in 2026, similar in shape
    # to the Jefferson/McCarthy situation.
    'Terry McLaurin': 1.20,
}


def apply_situational_adjustments(players):
    players = players.copy()
    multiplier = players['player_display_name'].map(SITUATIONAL_ADJUSTMENTS).fillna(1.0)
    players['projected_ppg'] = players['projected_ppg'] * multiplier
    players['projected_points'] = players['projected_ppg'] * players['projected_games']
    return players
