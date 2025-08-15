<?php
$shellgei = $_POST['shellgei'];
$problem = $_POST['problem'];

// デバッグ：PHPを実行するユーザ名
// $username = posix_getpwuid(posix_geteuid())['name'];
// file_put_contents("../debug.txt", $username, FILE_APPEND);

// 時間管理
$filename_time_ms = '../shellgei_time_ms.txt';
$shellgei_oldtime_ms = file_get_contents($filename_time_ms);
$shellgei_newtime_ms = microtime(true);
$time_ms_diff = (float)((float)$shellgei_newtime_ms - (float)$shellgei_oldtime_ms);
// file_put_contents("../debug_time_ms_diff.txt", $time_ms_diff, LOCK_EX);
if($time_ms_diff < (float)0.1) {
  $res['shellgei_output'] = "The server is busy(0.1s).";
  $res['shellgei_id'] = "-99";
  $res['shellgei_date'] = $shellgei_newtime;
  $res['shellgei_image'] = "";
  echo json_encode($res);
  exit();
}
file_put_contents($filename_time_ms, $shellgei_newtime_ms, LOCK_EX);

// \rを全て置換
$shellgei = str_replace('\r', '', $shellgei);
$problem = str_replace('\r', '', $problem);

// 実行したシェル芸のIDを取得
$filename_id = '../shellgei_id.txt';
$shellgei_id_str = file_get_contents($filename_id);
$shellgei_id = (int) $shellgei_id_str;
$shellgei_id = $shellgei_id + 1;
$shellgei_id_str = (string) $shellgei_id;
file_put_contents($filename_id, $shellgei_id_str, LOCK_EX);

// ログをファイルに書き込み
date_default_timezone_set('Asia/Tokyo');
$datetime = date('Y-m-d H:i:s');
$filename_log = '../shellgei_log.txt';
file_put_contents($filename_log, "\n", FILE_APPEND);
file_put_contents($filename_log, "SHELLGEI ID : ".$shellgei_id_str."\n", FILE_APPEND);
file_put_contents($filename_log, "date : ".$datetime."\n", FILE_APPEND);
file_put_contents($filename_log, "problem : ".$problem."\n", FILE_APPEND);
file_put_contents($filename_log, "cmd : ".str_replace(array("\r\n", "\r", "\n"), ' ', $shellgei)."\n", FILE_APPEND);

// コマンドを実行ファイルに書き込み
$filename_z = '../z.bash';
file_put_contents($filename_z, $shellgei);

// \rをすべて置換
$str = file_get_contents($filename_z);
$str = str_replace("\r", "", $str);
file_put_contents($filename_z, $str);

// dockerのコンテナを起動
shell_exec("sudo docker run -dit --rm --ipc=none --network=none theoldmoon0602/shellgeibot");

// コンテナのIDを取得
$cid = shell_exec("sudo docker ps | awk 'NR==2{print $1}'");

// 入力ファイルをコンテナ内にコピー
$cmd0 = "sudo docker cp ./input/$problem.txt $cid:/input.txt";
$cmd0 = str_replace(PHP_EOL, "", $cmd0);
shell_exec("$cmd0");

// 実行するファイルをコンテナ内にコピー
$cmd1 = "sudo docker cp $filename_z $cid:/";
$cmd1 = str_replace(PHP_EOL, "", $cmd1);
shell_exec("$cmd1");

// 画像を作成しておく
$cmd_tmp_image = "sudo docker exec $cid /bin/bash -c 'convert -size 200x200 xc:white media/output.jpg'";
$cmd_tmp_image = str_replace(PHP_EOL, "", $cmd_tmp_image);
shell_exec("$cmd_tmp_image");

// シェル芸を実行して結果を取得
$cmd2 = "timeout 10 python3 ../run_shellgei.py $cid 2>&1";
$cmd2 = str_replace(PHP_EOL, "", $cmd2);
$out = shell_exec("$cmd2");
$out = str_replace("\r", "", $out);
if(is_null($out)) $out = "NULL";
if(strlen($out) == 0) $out = "NULL";
if($out=="\n") $out = "NULL";
if($out=="\r") $out = "NULL";
$limit = 1000;
if(strlen($out) > $limit) $out = substr($out, 0, $limit);

// 判定するために出力を変換
$tmp_out = str_replace(" ", "SPACE", $out);
$tmp_out = str_replace("\r", "", $tmp_out);
$tmp_out = str_replace("\n", "NEWLINE", $tmp_out);
$tmp_out = str_replace("\t", "TAB", $tmp_out);
$tmp_out = str_replace("<", "LT", $tmp_out);
$tmp_out = str_replace(">", "GT", $tmp_out);

// 出力も記録
file_put_contents($filename_log, "output : ".$tmp_out."\n", FILE_APPEND);

// 画像を取得（Base64で変換）
$cmd_find_image = "sudo docker exec $cid /bin/bash -c 'find media'";
$cmd_find_image = str_replace(PHP_EOL, "", $cmd_find_image);
$output_find_image = shell_exec("$cmd_find_image");
$cmd_image = "";
if (strpos($output_find_image,'output.gif') !== false) {
  $cmd_image = "sudo docker exec $cid /bin/bash -c 'base64 -w 0 media/output.gif'";
} else {
  $cmd_image = "sudo docker exec $cid /bin/bash -c 'base64 -w 0 media/output.jpg'";
}
$cmd_image = str_replace(PHP_EOL, "", $cmd_image);
$output_image_base64 = shell_exec("$cmd_image");

// 画像も記録
// file_put_contents($filename_log, "output image : ".str_replace(array("\r\n", "\r", "\n"), ' ', $output_image_base64)."\n", FILE_APPEND);

// コンテナを削除
$cmd3 = "sudo docker rm -f $cid";
$cmd3 = str_replace(PHP_EOL, "", $cmd3);
shell_exec("$cmd3");

// 正誤判定
$answer_file_path =  "./output/$problem.txt";
$answer_file = file_get_contents($answer_file_path);
$tmp_answer = str_replace(" ", "SPACE", $answer_file);
$tmp_answer = str_replace("\r", "", $tmp_answer);
$tmp_answer = str_replace("\n", "NEWLINE", $tmp_answer);
$tmp_answer = str_replace("\t", "TAB", $tmp_answer);
$tmp_answer = str_replace("<", "LT", $tmp_answer);
$tmp_answer = str_replace(">", "GT", $tmp_answer);
$cmd_answer_image = "base64 -w 0 ./image/$problem.jpg";
$cmd_answer_image = str_replace(PHP_EOL, "", $cmd_answer_image);
$answer_image_base64 = shell_exec("$cmd_answer_image");
$cmd_judge_result = "python3 ../judge.py $tmp_out $output_image_base64 $tmp_answer $answer_image_base64 2>&1";
$cmd_judge_result = str_replace(PHP_EOL, "", $cmd_judge_result);
$judge_result = shell_exec("$cmd_judge_result");

// コマンドの実行結果を送り返す
$res['shellgei_output'] = $out;
$res['shellgei_id'] = $shellgei_id_str;
$res['shellgei_date'] = $datetime;
$res['shellgei_image'] = $output_image_base64;
$res['shellgei_judge'] = $judge_result;
echo json_encode($res);

// 時刻を記録
// $shellgei_newtime_ms = microtime(true);
// file_put_contents($filename_time_ms, $shellgei_newtime_ms, LOCK_EX);