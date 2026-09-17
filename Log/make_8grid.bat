@ECHO OFF
REM 8格拼贴：从 kaihetiao_4k_20m.mp4 裁孩子区域(1320x1410@1140,750) -> 912x990 x8格 -> 4K黑底
REM 取前 752s = 12 循环 (62.6s/loop)
E:\TestTools\ffmpeg\bin\ffmpeg.exe -hide_banner -y -i E:\TestTools\kaihetiao_4k_20m.mp4 -t 752 -filter_complex "[0:v]crop=1320:1410:1140:750,scale=912:990:flags=lanczos,fps=30,split=8[s0][s1][s2][s3][s4][s5][s6][s7];color=black:size=3840x2160:rate=30[base];[base][s0]overlay=24:45:shortest=1[t0];[t0][s1]overlay=984:45:shortest=1[t1];[t1][s2]overlay=1944:45:shortest=1[t2];[t2][s3]overlay=2904:45:shortest=1[t3];[t3][s4]overlay=24:1125:shortest=1[t4];[t4][s5]overlay=984:1125:shortest=1[t5];[t5][s6]overlay=1944:1125:shortest=1[t6];[t6][s7]overlay=2904:1125:shortest=1[out]" -map "[out]" -c:v libx264 -preset veryfast -b:v 18M -maxrate 20M -bufsize 40M -pix_fmt yuv420p -an E:\TestTools\kaihetiao_8grid_12m.mp4
ECHO EXITCODE=%ERRORLEVEL%
