# camera
python3 -m pytest -q --config=camera.yaml API/tests/settings/test_ping.py


# count file 
python -m pytest API/tests/ --collect-only | grep "<Module.*\.py" | wc -l  
# count test cases
python -mpytest API/tests --collect-only -q | tail -1

# 生成报告
allure generate allure-report/allure-results -o allure-report/http-report --clean

# 打开报告
allure open allure-report/http-report