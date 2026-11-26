name: 两地天气推送
on:
  schedule:
    - cron: '30 22 * * *'
    - cron: '0 11 * * *'
  workflow_dispatch:
    inputs:
      mode:
        description: '运行模式'
        required: true
        default: 'realtime'
        type: choice
        options:
          - realtime
          - midnight
permissions:
  contents: write
jobs:
  weather:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Set mode
        run: |
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            echo "MODE=${{ github.event.inputs.mode }}" >> $GITHUB_ENV
          elif [ "${{ github.event.schedule }}" = "0 11 * * *" ]; then
            echo "MODE=midnight" >> $GITHUB_ENV
          else
            echo "MODE=realtime" >> $GITHUB_ENV
          fi
      - name: Install Pillow
        run: pip install pillow
      - name: Download Chinese font
        run: wget -qO NotoSansCJKsc-Regular.otf https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf
      - name: Generate image
        env:
          SENDKEY: dummy
          QWKEY: ${{ secrets.QWKEY }}
        run: python weather.py "$MODE" no-send
      - name: Commit image
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add img
          git commit -m "weather image" || echo "nothing to commit"
          git push
      - name: Send to ServerChan
        env:
          SENDKEY: ${{ secrets.SENDKEY }}
          QWKEY: ${{ secrets.QWKEY }}
        run: python weather.py "$MODE"
