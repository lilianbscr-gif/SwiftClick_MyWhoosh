Set-Location "c:\Users\lilia\Documents\SwiftClick_MyWhoosh"
$log = "logs\review.log"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$ts] === Lancement research_review ===" | Out-File -Append -Encoding utf8 $log
python scripts\research_review.py 2>&1 | Out-File -Append -Encoding utf8 $log
