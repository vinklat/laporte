/* jshint 
    unused:false
*/

const locale = navigator.language;

const is_same_day = (date1, date2) => {
    return (
        date1.getUTCFullYear() === date2.getUTCFullYear() &&
        date1.getMonth() === date2.getMonth() &&
        date1.getDate() === date2.getDate()
    );
};

const renderTime = (time) => {
    var ret = `${time.toLocaleTimeString(locale)}`;
    const tnow = new Date();

    if (!is_same_day(time, tnow)) {
        ret = `${time.toLocaleDateString(locale).replace(/ /g, '&nbsp;')} ` + ret;
    }
    return (ret);
};

const fmtMSS = (s) => {
    return (s - (s %= 60)) / 60 + (9 < s ? ':' : ':0') + s;
};

const utfChars = '\u00A0-\u9999<>\&';
const utfEncode = (char) => ('&#' + char.charCodeAt(0) + ';');
const customEncode = {
    '\n': '<br/>',
    ' ': '&nbsp'
};
const customChars = Object.keys(customEncode).join('');

const encRegex = new RegExp(`[${utfChars}${customChars}]`, 'g');

const htmlEncode = (str) => {
    return str.replace(encRegex, function (c) {
        return customEncode[c] || utfEncode(c);
    });
};

const logTrClass = (level) => {
    const tableClass = {
        light: 'table-light',
        info: 'table-info',
        warning: 'table-warning',
        danger: 'table-danger'
    };

    const levels = {
        'DEBUG': tableClass.light,
        'WARNING': tableClass.warning,
        'CRITICAL': tableClass.danger,
        'ERROR': tableClass.danger,
        'default': tableClass.info
    };

    return levels[level] || levels.default;
};


const scrollToElement = (id, speed = 1000) => {
    $("html, body").animate({ scrollTop: $(id).offset().top }, speed);
};

const scrollToBottomAnimate = () => {
    scrollToElement('#log-end', 50);
};

const scrollToBottomInstant = () => {
    scrollToElement('#log-end', 1);
};

const checkboxChecked = (id) => {
    return ($(id).is(":checked"));
};

const followLogs = () => {
    return checkboxChecked('#followLogs');
};