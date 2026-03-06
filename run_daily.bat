@echo off
cd /d "C:\Users\mats\Dropbox\GAI\有名人のX投稿監視システム"

echo ================================
echo X有名人モニタリング 自動実行
echo ================================

echo.
echo [1/2] レポート生成・メール送信中...
python main.py

echo.
echo [2/2] GitHubにレポートをアップロード中...
git add docs/
git commit -m "レポート自動更新 %date%"
git push https://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@github.com/gamaken216/XwatchSystem.git master

echo.
echo ================================
echo 完了！
echo ================================
