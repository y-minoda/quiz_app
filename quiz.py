"""
東大数学 問題識別クイズ
使い方: streamlit run quiz.py
"""
import json
import random
from pathlib import Path

import streamlit as st
from PIL import Image

# ────── 定数 ──────
APP_DIR   = Path(__file__).parent
DATA_FILE = APP_DIR / 'data' / 'problems.json'
LABELS    = ['Ａ', 'Ｂ', 'Ｃ', 'Ｄ']


# ────── データ読み込み ──────
@st.cache_data
def load_problems() -> list[dict]:
    with open(DATA_FILE, encoding='utf-8') as f:
        return json.load(f)['problems']


def filter_problems(problems: list[dict], exam_type: str, y_from: int, y_to: int) -> list[dict]:
    pool = [p for p in problems if y_from <= p['year'] <= y_to]
    if exam_type != '両方':
        pool = [p for p in pool if p['type'] == exam_type]
    return pool


# ────── ラベル・画像 ──────
def problem_label(p: dict, show_type: bool = True) -> str:
    s = f'{p["year"]}年度　第{p["number"]}問'
    if show_type:
        s += f'（{p["type"]}）'
    return s


def load_image(p: dict) -> Image.Image:
    img_path = APP_DIR / p['image']
    return Image.open(str(img_path))


# ────── クイズ生成 ──────
def pick_distractors(pool: list[dict], q: dict, spread: int) -> list[dict]:
    """
    正解 q に対するダミー選択肢を3問選ぶ。
    spread: 正解の年度から ±spread 年以内を優先して選ぶ。
    不足する場合はプール全体から補う。
    """
    others = [p for p in pool
              if not (p['year'] == q['year'] and p['number'] == q['number'] and p['type'] == q['type'])]
    nearby = [p for p in others if abs(p['year'] - q['year']) <= spread]

    if len(nearby) >= 3:
        return random.sample(nearby, 3)

    # nearby が足りない場合：nearby を全部使い、残りを全体から補う
    nearby_keys = {(p['year'], p['type'], p['number']) for p in nearby}
    rest = [p for p in others if (p['year'], p['type'], p['number']) not in nearby_keys]
    random.shuffle(rest)
    return (nearby + rest)[:3]


def pick_year_distractors(pool: list[dict], q: dict, spread: int) -> list[dict]:
    """年度当てクイズ用ダミー（同種別から ±spread 年以内を優先）"""
    same = [y for y in pool if y['type'] == q['type'] and y['year'] != q['year']]
    nearby = [y for y in same if abs(y['year'] - q['year']) <= spread]
    if len(nearby) >= 3:
        return random.sample(nearby, 3)
    nearby_years = {y['year'] for y in nearby}
    rest = [y for y in same if y['year'] not in nearby_years]
    random.shuffle(rest)
    return (nearby + rest)[:3]


def pick_year_only_distractors(pool: list[dict], q: dict, spread: int) -> list[int]:
    """年度のみのダミー3年度を返す（重複なし）"""
    other_years = sorted({p['year'] for p in pool if p['year'] != q['year']})
    nearby = [y for y in other_years if abs(y - q['year']) <= spread]
    if len(nearby) >= 3:
        return random.sample(nearby, 3)
    rest = [y for y in other_years if y not in set(nearby)]
    random.shuffle(rest)
    return (nearby + rest)[:3]


def generate_split_question(pool: list[dict], exam_type: str, spread: int) -> dict:
    """mode=4: 問題画像 → 年度4択 ＋ 問番号を個別選択"""
    q = random.choice(pool)
    wrong_years = pick_year_only_distractors(pool, q, spread)
    year_choices = [q['year']] + wrong_years
    random.shuffle(year_choices)
    max_num = 6 if q['type'] == '理系' else 4
    return {
        'q': q,
        'year_choices': year_choices,
        'max_num': max_num,
        'mode': 4,
        'show_type': (exam_type == '両方'),
    }


def generate_year_question(pool: list[dict], spread: int) -> dict:
    """mode=3: 年度全体の問題一覧 → 年度を当てる"""
    # 年度×種別のユニーク一覧を作る
    year_entries = list({(p['year'], p['type']): {'year': p['year'], 'type': p['type']}
                         for p in pool}.values())
    q = random.choice(year_entries)
    wrongs = pick_year_distractors(year_entries, q, spread)
    choices = [{'year': q['year'], 'type': q['type'], 'correct': True}] + \
              [{'year': w['year'], 'type': w['type'], 'correct': False} for w in wrongs]
    random.shuffle(choices)
    return {'q': q, 'choices': choices, 'mode': 3, 'show_type': True}


def generate_question(pool: list[dict], mode: int, exam_type: str, spread: int) -> dict:
    """
    mode=1: 問題画像 → 年度・問番号（4択）
    mode=2: 年度・問番号 → 4つの問題画像から選ぶ
    spread: 選択肢の年度幅（±N年以内からダミーを選ぶ）
    """
    q = random.choice(pool)
    wrongs = pick_distractors(pool, q, spread)
    show_type = (exam_type == '両方')

    if mode == 1:
        choices = [{'label': problem_label(q, show_type), 'correct': True}] + \
                  [{'label': problem_label(w, show_type), 'correct': False} for w in wrongs]
    else:
        choices = [{'prob': q, 'correct': True}] + \
                  [{'prob': w, 'correct': False} for w in wrongs]

    random.shuffle(choices)
    return {'q': q, 'choices': choices, 'mode': mode, 'show_type': show_type}


# ────── セッション ──────
def init_state():
    for k, v in {'score': 0, 'total': 0, 'question': None,
                 'answered': False, 'selected_idx': None, 'last_settings': None,
                 'q_id': 0, 'selected_year_idx': None, 'selected_num': None}.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_question():
    st.session_state.question = None
    st.session_state.answered = False
    st.session_state.selected_idx = None
    st.session_state.selected_year_idx = None
    st.session_state.selected_num = None
    st.session_state.q_id += 1  # フォームkeyを変えてradioの選択状態をリセット


# ════════════════════════════════════════
def main():
    st.set_page_config(
        page_title='東大数学 問題識別クイズ',
        page_icon='📐',
        layout='wide',
        initial_sidebar_state='expanded',
    )
    init_state()

    # ── サイドバー ──────────────────────
    with st.sidebar:
        st.markdown('# 📐 東大数学クイズ')
        st.caption('問題の年度・問番号を当てるトレーニング')
        st.divider()

        app_mode = st.radio('', ['🎯 クイズ', '📖 勉強'],
                            horizontal=True, label_visibility='collapsed',
                            key='_app_mode')
        st.divider()

        if app_mode == '🎯 クイズ':
            mode = st.radio(
                'クイズモード',
                [1, 2, 3],
                format_func=lambda x: (
                    '① 問題を見て → 年度・問番号を当てる'
                    if x == 1 else
                    '② 年度・問番号を見て → 問題を選ぶ'
                    if x == 2 else
                    '③ 年度全体を見て → 年度を当てる'
                ),
            )
            split_mode = False
            if mode == 1:
                split_mode = st.radio(
                    '選択方式',
                    ['セット（4択）', '別々（年度・問番号を分けて選ぶ）'],
                    horizontal=True,
                ) == '別々（年度・問番号を分けて選ぶ）'
            exam_type = st.radio('種別', ['理系', '文系', '両方'])
            year_range = st.slider('出題年度範囲', 1980, 2025, (1980, 2025))

            st.divider()

            spread = st.slider(
                '選択肢の年度幅　±N年以内',
                min_value=1, max_value=45, value=45,
            )
            # 難易度表示
            if spread <= 5:
                st.caption('難易度：★★★　近い年度の問題が並ぶ')
            elif spread <= 15:
                st.caption('難易度：★★☆')
            else:
                st.caption('難易度：★☆☆　年度が離れた問題が並ぶ')

            st.divider()
            if st.session_state.total > 0:
                pct = st.session_state.score / st.session_state.total * 100
                st.metric('正答率', f'{pct:.0f}%',
                          f'{st.session_state.score}/{st.session_state.total} 問正解')
                st.progress(pct / 100)
            else:
                st.info('まだ出題されていません')

            if st.button('🔄 スコアリセット', use_container_width=True):
                st.session_state.score = 0
                st.session_state.total = 0
                reset_question()
                st.rerun()

        else:
            # 勉強モード設定
            study_type = st.radio('種別', ['理系', '文系'], key='_study_type')
            _all_probs = load_problems()
            study_years = sorted({p['year'] for p in _all_probs if p['type'] == study_type})

            # study_year_idx の初期化・クランプ
            if 'study_year_idx' not in st.session_state:
                st.session_state.study_year_idx = len(study_years) - 1
            st.session_state.study_year_idx = max(
                0, min(len(study_years) - 1, st.session_state.study_year_idx))

            # ウィジェットキーの初期化・有効値チェック
            for _k in ('_study_slider', '_study_select'):
                if _k not in st.session_state or st.session_state[_k] not in study_years:
                    st.session_state[_k] = study_years[st.session_state.study_year_idx]

            # on_change コールバック（ここで study_years が参照できる）
            def _sync_from_slider():
                year = st.session_state['_study_slider']
                if year in study_years:
                    idx = study_years.index(year)
                    st.session_state.study_year_idx = idx
                    st.session_state['_study_select'] = year

            def _sync_from_select():
                year = st.session_state['_study_select']
                if year in study_years:
                    idx = study_years.index(year)
                    st.session_state.study_year_idx = idx
                    st.session_state['_study_slider'] = year

            # 前/後ボタン
            col_prev, col_next = st.columns(2)
            with col_prev:
                if st.button('◀ 前の年度', use_container_width=True,
                             disabled=(st.session_state.study_year_idx == 0)):
                    new_idx = st.session_state.study_year_idx - 1
                    st.session_state.study_year_idx = new_idx
                    st.session_state['_study_slider'] = study_years[new_idx]
                    st.session_state['_study_select'] = study_years[new_idx]
                    st.rerun()
            with col_next:
                if st.button('後の年度 ▶', use_container_width=True,
                             disabled=(st.session_state.study_year_idx == len(study_years) - 1)):
                    new_idx = st.session_state.study_year_idx + 1
                    st.session_state.study_year_idx = new_idx
                    st.session_state['_study_slider'] = study_years[new_idx]
                    st.session_state['_study_select'] = study_years[new_idx]
                    st.rerun()

            # スライダー
            st.select_slider('年度スライダー', options=study_years,
                             key='_study_slider', on_change=_sync_from_slider)

            # プルダウン
            st.selectbox('年度を選ぶ', options=study_years,
                         key='_study_select', on_change=_sync_from_select)

            study_year = study_years[st.session_state.study_year_idx]

    # ── 問題プール ──────────────────────
    all_probs = load_problems()

    # ── 勉強モード（早期リターン） ──────────────────────
    if app_mode == '📖 勉強':
        st.markdown('# 📖 勉強モード')
        st.markdown(f'## {study_year}年度　{study_type}')
        st.divider()
        study_probs = sorted(
            [p for p in all_probs if p['type'] == study_type and p['year'] == study_year],
            key=lambda p: p['number'],
        )
        if not study_probs:
            st.warning('該当する問題が見つかりません。')
        else:
            mid = (len(study_probs) + 1) // 2
            col_l, col_r = st.columns(2)
            for col, probs in [(col_l, study_probs[:mid]), (col_r, study_probs[mid:])]:
                with col:
                    for p in probs:
                        st.subheader(f'第{p["number"]}問')
                        img = load_image(p)
                        st.image(img, use_container_width=True)
                        st.divider()
        return

    pool = filter_problems(all_probs, exam_type, year_range[0], year_range[1])

    if mode == 3:
        if len({(p['year'], p['type']) for p in pool}) < 4:
            st.error('年度が不足しています。年度範囲を広げてください。')
            return
    else:
        if len(pool) < 4:
            st.error('問題が不足しています。年度範囲や種別を広げてください。')
            return

    # 設定変更時はリセット
    cur_settings = (mode, split_mode, exam_type, year_range, spread)
    if st.session_state.last_settings != cur_settings:
        st.session_state.last_settings = cur_settings
        reset_question()

    # 新しい問題を生成
    if st.session_state.question is None:
        if mode == 3:
            st.session_state.question = generate_year_question(pool, spread)
        elif mode == 1 and split_mode:
            st.session_state.question = generate_split_question(pool, exam_type, spread)
        else:
            st.session_state.question = generate_question(pool, mode, exam_type, spread)

    qdata   = st.session_state.question
    q       = qdata['q']
    choices = qdata.get('choices', [])
    qmode   = qdata['mode']
    show_t  = qdata['show_type']

    # ── ヘッダー ──────────────────────
    col_title, col_score = st.columns([3, 1])
    with col_title:
        st.markdown('# 東大数学 問題識別クイズ')
    with col_score:
        if st.session_state.total > 0:
            st.metric('正解数',
                      f'{st.session_state.score} / {st.session_state.total}',
                      f'{st.session_state.score/st.session_state.total*100:.0f}%')
    st.divider()

    # ════════════════════════════════════
    if qmode == 1:
        # ── モード①: 問題画像 → 年度・問番号 ──
        st.subheader('❓ この問題は何年度の第何問でしょう？')
        if show_t:
            st.caption(f'種別: {q["type"]}')

        # 問題画像（全幅）
        img = load_image(q)
        st.image(img, use_container_width=True)

        st.divider()

        # 4択フォーム
        # ※ st.form内でradio選択してもrereunされないため、
        #   submit buttonのdisabledはst.session_state.answeredのみで判定する
        with st.form(f'quiz_form_{st.session_state.q_id}'):
            sel = st.radio(
                '年度と問番号を選んでください：',
                options=range(len(choices)),
                format_func=lambda i: f'{LABELS[i]}　　{choices[i]["label"]}',
                index=None,
                disabled=st.session_state.answered,
            )
            submitted = st.form_submit_button(
                '✅ 答え合わせ',
                type='primary',
                disabled=st.session_state.answered,
                use_container_width=True,
            )

        if submitted and not st.session_state.answered:
            if sel is None:
                st.warning('選択肢を選んでから「答え合わせ」を押してください。')
                st.stop()
        if submitted and sel is not None and not st.session_state.answered:
            st.session_state.selected_idx = sel
            st.session_state.answered = True
            if choices[sel]['correct']:
                st.session_state.score += 1
            st.session_state.total += 1
            st.rerun()

    # ════════════════════════════════════
    elif qmode == 2:
        # ── モード②: 年度・問番号 → 4択の問題画像 ──
        st.subheader('❓ 次の問題の問題文はどれでしょう？')
        st.markdown(f'## {q["year"]}年度　第{q["number"]}問　【{q["type"]}】')
        st.divider()

        # 4問を 2×2 グリッドで表示
        row1 = st.columns(2)
        row2 = st.columns(2)
        grid = [row1[0], row1[1], row2[0], row2[1]]

        for i, (col, c) in enumerate(zip(grid, choices)):
            with col:
                st.markdown(f'### {LABELS[i]}')
                img = load_image(c['prob'])
                st.image(img, use_container_width=True)

        st.divider()

        # 選択フォーム
        with st.form(f'quiz_form_{st.session_state.q_id}'):
            sel = st.radio(
                '正しい問題文を選んでください：',
                options=range(len(choices)),
                format_func=lambda i: LABELS[i],
                index=None,
                horizontal=True,
                disabled=st.session_state.answered,
            )
            submitted = st.form_submit_button(
                '✅ 答え合わせ',
                type='primary',
                disabled=st.session_state.answered,
                use_container_width=True,
            )

        if submitted and not st.session_state.answered:
            if sel is None:
                st.warning('選択肢を選んでから「答え合わせ」を押してください。')
                st.stop()
        if submitted and sel is not None and not st.session_state.answered:
            st.session_state.selected_idx = sel
            st.session_state.answered = True
            if choices[sel]['correct']:
                st.session_state.score += 1
            st.session_state.total += 1
            st.rerun()

    # ════════════════════════════════════
    elif qmode == 3:
        # ── モード③: 年度全体の問題一覧 → 年度を当てる ──
        st.subheader('❓ この年度全体の問題は何年度でしょう？')
        st.caption(f'種別: {q["type"]}')

        year_probs = sorted(
            [p for p in pool if p['year'] == q['year'] and p['type'] == q['type']],
            key=lambda p: p['number'],
        )
        mid = (len(year_probs) + 1) // 2
        col_l, col_r = st.columns(2)
        for col, probs in [(col_l, year_probs[:mid]), (col_r, year_probs[mid:])]:
            with col:
                for p in probs:
                    st.subheader(f'第{p["number"]}問')
                    st.image(load_image(p), use_container_width=True)

        st.divider()

        with st.form(f'quiz_form_{st.session_state.q_id}'):
            sel = st.radio(
                '年度を選んでください：',
                options=range(len(choices)),
                format_func=lambda i: f'{LABELS[i]}　　{choices[i]["year"]}年度',
                index=None,
                disabled=st.session_state.answered,
            )
            submitted = st.form_submit_button(
                '✅ 答え合わせ',
                type='primary',
                disabled=st.session_state.answered,
                use_container_width=True,
            )

        if submitted and not st.session_state.answered:
            if sel is None:
                st.warning('選択肢を選んでから「答え合わせ」を押してください。')
                st.stop()
        if submitted and sel is not None and not st.session_state.answered:
            st.session_state.selected_idx = sel
            st.session_state.answered = True
            if choices[sel]['correct']:
                st.session_state.score += 1
            st.session_state.total += 1
            st.rerun()

    # ════════════════════════════════════
    else:
        # ── モード④: 問題画像 → 年度と問番号を別々に当てる ──
        y_choices = qdata['year_choices']
        max_num   = qdata['max_num']

        st.subheader('❓ この問題は何年度の第何問でしょう？')
        if show_t:
            st.caption(f'種別: {q["type"]}')

        img = load_image(q)
        st.image(img, use_container_width=True)

        st.divider()

        with st.form(f'quiz_form_{st.session_state.q_id}'):
            col_y, col_n = st.columns(2)
            with col_y:
                sel_year = st.radio(
                    '年度を選んでください：',
                    options=range(len(y_choices)),
                    format_func=lambda i: f'{LABELS[i]}　{y_choices[i]}年度',
                    index=None,
                    disabled=st.session_state.answered,
                )
            with col_n:
                sel_num = st.radio(
                    '問番号を選んでください：',
                    options=range(1, max_num + 1),
                    format_func=lambda i: f'第{i}問',
                    index=None,
                    disabled=st.session_state.answered,
                )
            submitted = st.form_submit_button(
                '✅ 答え合わせ',
                type='primary',
                disabled=st.session_state.answered,
                use_container_width=True,
            )

        if submitted and not st.session_state.answered:
            if sel_year is None or sel_num is None:
                st.warning('年度と問番号の両方を選んでから「答え合わせ」を押してください。')
                st.stop()
        if submitted and sel_year is not None and sel_num is not None and not st.session_state.answered:
            st.session_state.selected_year_idx = sel_year
            st.session_state.selected_num      = sel_num
            st.session_state.answered = True
            if y_choices[sel_year] == q['year'] and sel_num == q['number']:
                st.session_state.score += 1
            st.session_state.total += 1
            st.rerun()

    # ════════════════════════════════════
    # ── 結果表示 ──────────────────────
    if st.session_state.answered:
        if qmode == 4:
            # ── モード④の結果 ──
            y_choices  = qdata['year_choices']
            sel_yi     = st.session_state.selected_year_idx
            sel_n      = st.session_state.selected_num
            year_ok    = (y_choices[sel_yi] == q['year'])
            num_ok     = (sel_n == q['number'])

            if year_ok and num_ok:
                st.success(f'✅ **正解！** {problem_label(q, show_t)}')
            else:
                y_str = (f'{y_choices[sel_yi]}年度　✅' if year_ok
                         else f'{y_choices[sel_yi]}年度　❌　→ 正解：{q["year"]}年度')
                n_str = (f'第{sel_n}問　✅' if num_ok
                         else f'第{sel_n}問　❌　→ 正解：第{q["number"]}問')
                st.error(f'❌ **不正解**\n\n年度：{y_str}\n\n問番号：{n_str}')

        else:
            # ── モード①②③の結果 ──
            sel_idx     = st.session_state.selected_idx
            is_correct  = choices[sel_idx]['correct']
            correct_idx = next(i for i, c in enumerate(choices) if c['correct'])

            if is_correct:
                if qmode == 3:
                    st.success(f'✅ **正解！** {q["year"]}年度（{q["type"]}）')
                else:
                    st.success(f'✅ **正解！** {problem_label(q, show_t)}')
            else:
                if qmode == 1:
                    wrong_label = choices[sel_idx]['label']
                    st.error(
                        f'❌ **不正解**\n\n'
                        f'あなたの答え：{LABELS[sel_idx]}　{wrong_label}\n\n'
                        f'正解：{LABELS[correct_idx]}　{problem_label(q, show_t)}'
                    )
                elif qmode == 2:
                    st.error(
                        f'❌ **不正解**\n\n'
                        f'あなたの答え：{LABELS[sel_idx]}\n\n'
                        f'正解：{LABELS[correct_idx]}　({problem_label(q, True)})'
                    )
                else:
                    st.error(
                        f'❌ **不正解**\n\n'
                        f'あなたの答え：{LABELS[sel_idx]}　{choices[sel_idx]["year"]}年度\n\n'
                        f'正解：{LABELS[correct_idx]}　{q["year"]}年度'
                    )

        # この年度の全問題を勉強モードで見るボタン
        study_year_val  = q['year']
        study_type_val  = q['type']
        if st.button(f'📖 {study_year_val}年度（{study_type_val}）の全問題を見る',
                     use_container_width=True):
            _all = load_problems()
            s_years = sorted({p['year'] for p in _all if p['type'] == study_type_val})
            idx = s_years.index(study_year_val) if study_year_val in s_years else len(s_years) - 1
            st.session_state['_app_mode']    = '📖 勉強'
            st.session_state['_study_type']  = study_type_val
            st.session_state.study_year_idx  = idx
            st.session_state['_study_slider'] = study_year_val
            st.session_state['_study_select'] = study_year_val
            st.rerun()

        st.button('次の問題へ →', on_click=reset_question, type='primary', use_container_width=True)


if __name__ == '__main__':
    main()
