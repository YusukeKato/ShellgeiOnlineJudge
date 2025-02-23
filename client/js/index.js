// パラメータ
var version = 1075;
const limit_length = parseInt(1000);
var mainUrl = 'https://shellgei-online-judge.com/';
var is_enable_button = true;

// 使用データ変数
var problemNum = 'GENERAL-00000001';
var shellgeiResult = 'NULL';
var shellgeiID = '0';
var shellgeiDate = '0';
var shellgeiImage = '';
var shellgeiJudge = 'null';

// HTMLの要素を編集
var userOutput = document.getElementById('userOutputText');
var resultText = document.getElementById('resultText');
var st = document.getElementById('shellgeiText');
var selected = document.getElementById('selectedText');
var outputImageParent = document.getElementById('outputImage');
var resultImageParent = document.getElementById('resultImage');

// Ctrl+Enterで投稿
var keydownCtrl = false;
var keydownEnter = false;

// タイムアウト処理用関数
function timeout() {
    clearInterval(timerId);
    shellgeiResult = 'timeout: 5000ms\n';
    let timeoutTxt = shellgeiResult;
    userOutput.innerHTML = timeoutTxt;
    resultText.innerHTML = timeoutTxt;
    st.innerHTML = timeoutTxt;
}

// reference: https://kinocolog.com/javascript_first_last_slice/
function deleteNewline(text_strings) {
    // 先頭の改行と空白を除去
    for(let i = 0; i < text_strings.length; i++) {
        if(text_strings.charAt(i) == '\n' || text_strings.charAt(i) == ' ') {
            text_strings = text_strings.slice(1);
            i--;
        } else {
            break;
        }
    }
    // 末尾の改行と空白を除去
    for(let i = text_strings.length-1; i >= 0; i--) {
        if(text_strings.charAt(i) == '\n' || text_strings.charAt(i) == ' ') {
            text_strings = text_strings.slice(0, -1);
        } else {
            break;
        }
    }
    return text_strings;
}

// 問題データ取得関数
// reference: https://munibus.hatenablog.com/entry/2022/09/30/225938
function getText(objectId, fileName, addFlag, defaultString) {
    let result = document.getElementById(objectId);
    let xhr = new XMLHttpRequest();
    xhr.open('GET', fileName, true);
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                result.textContent = '';
                let lines = xhr.responseText.split('\n');
                let line = '';
                for(i = 0; i < lines.length; i++) {
                    if(i != lines.length-1) line += lines[i] + '\n';
                }
                line = line.replace(/</g, '&lt;');
                line = line.replace(/>/g, '&gt;');
                if (addFlag == true) {
                    result.insertAdjacentHTML('afterbegin', defaultString+line);
                }
                else if (addFlag == false) {
                    result.insertAdjacentHTML('afterbegin', line);
                }
                // console.log(objectId+", "+fileName+": "+line);
            } else {
                result.textContent = 'Error: Could not get problem files!!';
            }
        } else {
            result.textContent = 'LOADING......';
        }
    }
    xhr.send(null);
}

function getProblemNum() {
    getText('generalProblem', mainUrl+'scripts/cnt_general_num.txt?version='+version, true, "GENERAL: ");
    getText('exerciseProblem', mainUrl+'scripts/cnt_execise_num.txt?version='+version, true, "EXERCISE: ");
    getText('imageProblem', mainUrl+'scripts/cnt_image_num.txt?version='+version, true, "IMAGE: ");
}

window.addEventListener("load", function() {
    getProblemNum();
});

// 問題選択を一つ前と後ろに進めるボタン
function selectPreFunc(selectForm) {
    for(var i = 0; i < selectForm.options.length; i++) {
        if(i-1 >= 0 && selectForm.options[i].selected == true) {
            selectForm.options[i].selected = false;
            selectForm.options[i-1].selected = true;
            return;
        }
    }
}
function selectNextFunc(selectForm) {
    for(var i = 0; i < selectForm.options.length; i++) {
        if(i+1 < selectForm.options.length && selectForm.options[i].selected == true) {
            selectForm.options[i].selected = false;
            selectForm.options[i+1].selected = true;
            return;
        }
    }
}
function selectPre1() {
    var selectForm1 = document.getElementById('selectForm1');
    selectPreFunc(selectForm1);
}
function selectNext1() {
    var selectForm1 = document.getElementById('selectForm1');
    selectNextFunc(selectForm1);
}
function selectPre2() {
    var selectForm2 = document.getElementById('selectForm2');
    selectPreFunc(selectForm2);
}
function selectNext2() {
    var selectForm2 = document.getElementById('selectForm2');
    selectNextFunc(selectForm2);
}
function selectPre3() {
    var selectForm3 = document.getElementById('selectForm3');
    selectPreFunc(selectForm3);
}
function selectNext3() {
    var selectForm3 = document.getElementById('selectForm3');
    selectNextFunc(selectForm3);
}
var selectPreButton1 = document.getElementById('selectPre1');
selectPreButton1.addEventListener('click', selectPre1);
var selectNextButton1 = document.getElementById('selectNext1');
selectNextButton1.addEventListener('click', selectNext1);
var selectPreButton2 = document.getElementById('selectPre2');
selectPreButton2.addEventListener('click', selectPre2);
var selectNextButton2 = document.getElementById('selectNext2');
selectNextButton2.addEventListener('click', selectNext2);
var selectPreButton3 = document.getElementById('selectPre3');
selectPreButton3.addEventListener('click', selectPre3);
var selectNextButton3 = document.getElementById('selectNext3');
selectNextButton3.addEventListener('click', selectNext3);

// 問題選択処理用関数
function selectClickFunc(problemNum_arg) {
    problemNum = problemNum_arg;
    // テキスト更新
    if(is_jp) {
        getText('problemText', mainUrl+'problem_jp/'+problemNum+'.txt?version='+version, false);
    } else {
        getText('problemText', mainUrl+'problem_en/'+problemNum+'.txt?version='+version, false);
    }
    getText('inputText', mainUrl+'input/'+problemNum+'.txt?version='+version, false);
    getText('outputText', mainUrl+'output/'+problemNum+'.txt?version='+version, false);
    // 想定画像を更新
    while (outputImageParent.firstChild) {
        outputImageParent.removeChild(outputImageParent.firstChild);
    }
    let img_outputImage = document.createElement('img');
    img_outputImage.src = mainUrl+'problem_images/'+problemNum+'.jpg?version='+version;
    img_outputImage.alt = 'output image';
    img_outputImage.id = 'output_image_child';
    outputImageParent.appendChild(img_outputImage);
    // 選択した問題IDを更新
    selected.innerHTML = problemNum;
    // 余計な空白と改行を削除
    userOutput.innerHTML = deleteNewline(userOutput.innerHTML);
    resultText.innerHTML = deleteNewline(resultText.innerHTML);
    st.innerHTML = deleteNewline(st.innerHTML);
}
function selectClick1() {
    let problem = document.getElementById('selectForm1');
    selectClickFunc(problem.value);
}
function selectClick2() {
    let problem = document.getElementById('selectForm2');
    selectClickFunc(problem.value);
}
function selectClick3() {
    let problem = document.getElementById('selectForm3');
    selectClickFunc(problem.value);
}
var selectButton1 = document.getElementById('selectButton1');
selectButton1.addEventListener('click', selectClick1);
var selectButton2 = document.getElementById('selectButton2');
selectButton2.addEventListener('click', selectClick2);
var selectButton3 = document.getElementById('selectButton3');
selectButton3.addEventListener('click', selectClick3);

// 入力されたシェル芸をサーバに送って実行結果をもらう関数
// reference: https://brainlog.jp/programming/javascript/post-3129/
function postSend(shellgei) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('shellgei', shellgei);
        formData.append('problemNum', problemNum);
        fetch(mainUrl+'connection.php', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(res => {
            if (res.shellgei != null) {
                shellgeiResult = res.shellgei.toString();
                shellgeiID = res.shellgei_id.toString();
                shellgeiDate = res.shellgei_date.toString();
                shellgeiImage = res.shellgei_image.toString();
                shellgeiJudge = res.shellgei_judge.toString();
                resolve("resolve");
            } else {
                throw new Error("response error : null");
            }
        })
        .catch(error => {
            console.log(error);
            reject("reject");
        });
    });
}

// reference: https://qiita.com/yasumodev/items/e1708f01ff87692185cd
function ImageToBase64(img, mime_type, id_name) {
    let canvasElement = document.getElementById(id_name); 
    if(canvasElement) canvasElement.remove();
    let canvas = document.createElement('canvas');
    canvas.id = id_name;
    canvas.width  = img.width;
    canvas.height = img.height;
    var ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    return canvas.toDataURL(mime_type);
}

// シェル芸の実行処理用関数
async function submitClick() {
    // ボタンの連打防止
    if(is_enable_button == false) {
        userOutput.innerHTML = "No buttons can be pressed in succession";
        resultText.innerHTML = "No buttons can be pressed in succession.";
        st.innerHTML = "No buttons can be pressed in succession.";
        return;
    }

    // 実行を開始したらボタンを無効にする
    // 3秒後に有効にする
    is_enable_button = false;
    let fn = function() {
        is_enable_button = true;
    };
    setTimeout(fn, 3000);

    // 実行中に表示を切り替え
    userOutput.innerHTML = "Running...";
    resultText.innerHTML = "Running...";
    st.innerHTML = "Running...";

    // 入力されたシェル芸の前処理
    var cmdline = document.getElementById('cmdline');
    cmdline.value = cmdline.value.replace(/\r/g, '');
    cmdline.value = cmdline.value.trim();
    cmdline.value = cmdline.value.replace(/\n$/g,'');
    
    // 入力されたシェル芸が1文字以上1000文字未満であれば実行
    if(cmdline.value.length > limit_length) {
        userOutput.innerHTML = "Exceeded character limit: 1000";
        resultText.innerHTML = "Exceeded character limit: 1000";
        st.innerHTML = "Exceeded character limit: 1000";
    } else if(cmdline.value.length == 0 || cmdline.value == '\n' || cmdline.value == '\r' || cmdline.value == ' ') {
        userOutput.innerHTML = "Error: No input";
        resultText.innerHTML = "Error: No input";
        st.innerHTML = "Error: No input";
    } else {
        // タイムアウトを設定して実行
        timerId = setInterval('timeout()', 10000);
        const txt = await postSend(cmdline.value + ' | head -n1000');
        clearInterval(timerId);

        // 実行したシェル芸の文字列の処理
        var replacedCmdline = cmdline.value;
        replacedCmdline = replacedCmdline.replace(/</g, '&lt;');
        replacedCmdline = replacedCmdline.replace(/>/g, '&gt;');
        st.innerHTML = 'SHELLGEI ID : ' + shellgeiID + '\nDATE : ' + shellgeiDate + ' (JST)\n' + 'COMMAND : ' + replacedCmdline;

        // 実行結果の確認
        if(shellgeiResult.length != 0 || shellgeiResult != null) {
            shellgeiResult = shellgeiResult.replace(/</g, '&lt;');
            shellgeiResult = shellgeiResult.replace(/>/g, '&gt;');
            userOutput.innerHTML = shellgeiResult;
        } else {
            userOutput.innerHTML = "ERROR : NULL";
        }

        // 出力結果の画像を表示
        while (resultImageParent.firstChild) {
            resultImageParent.removeChild(resultImageParent.firstChild);
        }
        let img_resultImage = document.createElement('img');
        shellgeiImage = 'data:image/jpeg;base64,'+shellgeiImage;
        img_resultImage.src = shellgeiImage;
        img_resultImage.alt = 'result image';
        img_resultImage.id = 'result_img_child';
        resultImageParent.appendChild(img_resultImage);
	
        shellgeiJudge = shellgeiJudge.replace('\n', '');
        shellgeiJudge = shellgeiJudge.replace('\r', '');

        // 正誤判定
        if(shellgeiJudge.indexOf("1") != -1) {
            if(is_jp) {
                resultText.innerHTML = "正解 !!😄!!";
            } else {
                resultText.innerHTML = "Correct !!😄!!";
            }
	} else {
            if(is_jp) {
                resultText.innerHTML = "不正解 ...😭...(" + shellgeiJudge + ")";
            } else {
                resultText.innerHTML = "Incorrect ...😭...(" + shellgeiJudge + ")";
            }
        }

        // console.log("shellgeiJudge: "+shellgeiJudge);
        // console.log("shellgeiResult: "+shellgeiResult);
        // console.log("shellgeiImage: "+shellgeiImage);
    }
}

// Ctrl+Enterで投稿
// 参考：https://developer.mozilla.org/ja/docs/Games/Tutorials/2D_Breakout_game_pure_JavaScript/Paddle_and_keyboard_controls
document.addEventListener("keydown", keyDownHandler, false);
function keyDownHandler(e) {
    if (e.ctrlKey) {
        keydownCtrl = true;
    }
    if (e.key === 'Enter') {
        keydownEnter = true;
    }
    if (keydownCtrl && keydownEnter) {
        keydownCtrl = false;
        keydownEnter = false;
        submitClick();
    }
}

// 実行ボタンの設定
var submitButton = document.getElementById('submitButton');
submitButton.addEventListener('click', submitClick);

// コマンドを入力するボタン
// abcdefghijklmnopqrstuvwxyz
// a
function input_awk() {
    input_command("awk '{}' ");
}
// c
function input_cat() {
    input_command("cat ");
}
function input_convert() {
    input_command("convert ");
}
function input_cut() {
    input_command("cut ");
}
// e
function input_echo() {
    input_command("echo ");
}
// f
function input_ffmpeg() {
    input_command("ffmpeg ");
}
function input_find() {
    input_command("find ");
}
function input_for() {
    input_command("for i in {1..10};do echo $i;done ");
}
// g
function input_grep() {
    input_command("grep ");
}
// l
function input_ls() {
    input_command("ls ");
}
// p
function input_ps() {
    input_command("ps ");
}
// s
function input_sed() {
    input_command("sed 's///' ");
}
function input_seq() {
    input_command("seq ");
}
function input_sort() {
    input_command("sort ");
}
// t
function input_tail() {
    input_command("tail ");
}
function input_textimg() {
    input_command("textimg ");
}
// u
function input_uniq() {
    input_command("uniq ");
}
// w
function input_wc() {
    input_command("wc ");
}
// other
function input_space() {
    input_command(" ");
}
function input_pipe() {
    input_command("|");
}
function input_hyphen() {
    input_command("-");
}
function input_plus() {
    input_command("+");
}
function input_equal() {
    input_command("=");
}
function input_under() {
    input_command("_");
}
function input_exclamation() {
    input_command("!");
}
function input_question() {
    input_command("?");
}
function input_single_quote() {
    input_command("'");
}
function input_double_quote() {
    input_command('"');
}
function input_back_quote() {
    input_command("`");
}
function input_parentheses_left() {
    input_command("(");
}
function input_parentheses_right() {
    input_command(")");
}
function input_square_left() {
    input_command("[");
}
function input_square_right() {
    input_command("]");
}
function input_curly_left() {
    input_command("{");
}
function input_curly_right() {
    input_command("}");
}
function input_slash() {
    input_command("/");
}
function input_back_slash() {
    input_command("\\");
}
function input_greater_then() {
    input_command(">");
}
function input_less_then() {
    input_command("<");
}
function input_asterisk() {
    input_command("*");
}
function input_dollar() {
    input_command("$");
}
function input_at() {
    input_command("@");
}
function input_dot() {
    input_command(".");
}
function input_comma() {
    input_command(",");
}
function input_sharp() {
    input_command("#");
}
function input_colon() {
    input_command(":");
}
function input_semicolon() {
    input_command(";");
}
function input_txt_path() {
    input_command("input.txt ");
}
function input_img_path() {
    input_command("/media/output.jpg ");
}
function input_gif_path() {
    input_command("/media/output.gif ");
}
// main function
function input_command(cmd_str) {
    var cmdline = document.getElementById('cmdline');
    cmdline.value = cmdline.value + cmd_str;
}
function delete_command_one() {
    var cmdline = document.getElementById('cmdline');
    cmdline.value = cmdline.value.slice(0, cmdline.value.length - 1);
}
function delete_command_all() {
    var cmdline = document.getElementById('cmdline');
    cmdline.value = "";
}

// abcdefghijklmnopqrstuvwxyz
// a
var commandButton_awk = document.getElementById('command-awk');
commandButton_awk.addEventListener('click', input_awk);
// c
var commandButton_cat = document.getElementById('command-cat');
commandButton_cat.addEventListener('click', input_cat);
var commandButton_convert = document.getElementById('command-convert');
commandButton_convert.addEventListener('click', input_convert);
var commandButton_cut = document.getElementById('command-cut');
commandButton_cut.addEventListener('click', input_cut);
// e
var commandButton_echo = document.getElementById('command-echo');
commandButton_echo.addEventListener('click', input_echo);
// f
var commandButton_ffmpeg = document.getElementById('command-ffmpeg');
commandButton_ffmpeg.addEventListener('click', input_ffmpeg);
var commandButton_find = document.getElementById('command-find');
commandButton_find.addEventListener('click', input_find);
// g
var commandButton_grep = document.getElementById('command-grep');
commandButton_grep.addEventListener('click', input_grep);
// l
var commandButton_ls = document.getElementById('command-ls');
commandButton_ls.addEventListener('click', input_ls);
// p
var commandButton_ps = document.getElementById('command-ps');
commandButton_ps.addEventListener('click', input_ps);
// s
var commandButton_sed = document.getElementById('command-sed');
commandButton_sed.addEventListener('click', input_sed);
var commandButton_seq = document.getElementById('command-seq');
commandButton_seq.addEventListener('click', input_seq);
var commandButton_sort = document.getElementById('command-sort');
commandButton_sort.addEventListener('click', input_sort);
// t
var commandButton_tail = document.getElementById('command-tail');
commandButton_tail.addEventListener('click', input_tail);
var commandButton_textimg = document.getElementById('command-textimg');
commandButton_textimg.addEventListener('click', input_textimg);
// u
var commandButton_uniq = document.getElementById('command-uniq');
commandButton_uniq.addEventListener('click', input_uniq);
// w
var commandButton_wc = document.getElementById('command-wc');
commandButton_wc.addEventListener('click', input_wc);
// other
var commandButton_space = document.getElementById('command-space');
commandButton_space.addEventListener('click', input_space);
var commandButton_pipe = document.getElementById('command-pipe');
commandButton_pipe.addEventListener('click', input_pipe);
var commandButton_hyphen = document.getElementById('command-hyphen');
commandButton_hyphen.addEventListener('click', input_hyphen);
var commandButton_plus = document.getElementById('command-plus');
commandButton_plus.addEventListener('click', input_plus);
var commandButton_equal = document.getElementById('command-equal');
commandButton_equal.addEventListener('click', input_equal);
var commandButton_under = document.getElementById('command-under');
commandButton_under.addEventListener('click', input_under);
var commandButton_exclamation = document.getElementById('command-exclamation');
commandButton_exclamation.addEventListener('click', input_exclamation);
var commandButton_question = document.getElementById('command-question');
commandButton_question.addEventListener('click', input_question);
var commandButton_single_quote = document.getElementById('command-single-quote');
commandButton_single_quote.addEventListener('click', input_single_quote);
var commandButton_double_quote = document.getElementById('command-double-quote');
commandButton_double_quote.addEventListener('click', input_double_quote);
var commandButton_back_quote = document.getElementById('command-back-quote');
commandButton_back_quote.addEventListener('click', input_back_quote);
var commandButton_parentheses_left = document.getElementById('command-parentheses-left');
commandButton_parentheses_left.addEventListener('click', input_parentheses_left);
var commandButton_parentheses_right = document.getElementById('command-parentheses-right');
commandButton_parentheses_right.addEventListener('click', input_parentheses_right);
var commandButton_square_left = document.getElementById('command-square-left');
commandButton_square_left.addEventListener('click', input_square_left);
var commandButton_square_right = document.getElementById('command-square-right');
commandButton_square_right.addEventListener('click', input_square_right);
var commandButton_curly_left = document.getElementById('command-curly-left');
commandButton_curly_left.addEventListener('click', input_curly_left);
var commandButton_curly_right = document.getElementById('command-curly-right');
commandButton_curly_right.addEventListener('click', input_curly_right);
var commandButton_slash = document.getElementById('command-slash');
commandButton_slash.addEventListener('click', input_slash);
var commandButton_back_slash = document.getElementById('command-back-slash');
commandButton_back_slash.addEventListener('click', input_back_slash);
var commandButton_greater_then = document.getElementById('command-greater-then');
commandButton_greater_then.addEventListener('click', input_greater_then);
var commandButton_less_then = document.getElementById('command-less-then');
commandButton_less_then.addEventListener('click', input_less_then);
var commandButton_asterisk = document.getElementById('command-asterisk');
commandButton_asterisk.addEventListener('click', input_asterisk);
var commandButton_dollar = document.getElementById('command-dollar');
commandButton_dollar.addEventListener('click', input_dollar);
var commandButton_at = document.getElementById('command-at');
commandButton_at.addEventListener('click', input_at);
var commandButton_dot = document.getElementById('command-dot');
commandButton_dot.addEventListener('click', input_dot);
var commandButton_comma = document.getElementById('command-comma');
commandButton_comma.addEventListener('click', input_comma);
var commandButton_sharp = document.getElementById('command-sharp');
commandButton_sharp.addEventListener('click', input_sharp);
var commandButton_colon = document.getElementById('command-colon');
commandButton_colon.addEventListener('click', input_colon);
var commandButton_semicolon = document.getElementById('command-semicolon');
commandButton_semicolon.addEventListener('click', input_semicolon);
var commandButton_txt_path = document.getElementById('command-txt-path');
commandButton_txt_path.addEventListener('click', input_txt_path);
var commandButton_img_path = document.getElementById('command-img-path');
commandButton_img_path.addEventListener('click', input_img_path);
var commandButton_gif_path = document.getElementById('command-gif-path');
commandButton_gif_path.addEventListener('click', input_gif_path);

var commandButton_delete_one_cmd = document.getElementById('delete-command-one');
commandButton_delete_one_cmd.addEventListener('click', delete_command_one);
var commandButton_delete_all_cmd = document.getElementById('delete-command-all');
commandButton_delete_all_cmd.addEventListener('click', delete_command_all);
