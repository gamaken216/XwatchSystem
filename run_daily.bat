@echo off
cd /d "C:\Users\mats\Dropbox\GAI\有名人のX投稿監視システム"
echo レポート生成・メール送信中...
python main.py

echo.
echo GitHubにレポートをアップロード中...
git add docs/
git commit -m "レポート自動更新 %date%"
git push origin master

echo.
echo 完了！
