/* global React, ReactDOM, arco, arcoicon */
// Build with esbuild: --loader:.jsx=jsx --target=es2019 --format=iife --minify.

const {
  Alert,
  Button,
  Checkbox,
  DatePicker,
  Descriptions,
  Input,
  Message,
  Radio,
  Result,
  Spin,
  Upload,
} = arco;
const {
  IconCheck,
  IconClose,
  IconDownload,
  IconRefresh,
  IconUpload,
} = arcoicon;
const { useEffect, useRef, useState } = React;

const rootElement = document.getElementById('batch-root');
const token = window.location.hash.slice(1);
if (token) {
  try {
    window.history.replaceState(
      null,
      '',
      window.location.pathname + window.location.search,
    );
  } catch (_) {
    // Embedded WebViews may prohibit history mutation.
  }
}

async function requestApi(path, options = {}) {
  if (!token) {
    throw new Error('请从对话中的群发任务入口打开本机表单。');
  }
  const headers = new Headers(options.headers || {});
  headers.set('X-Batch-Context', token);
  let response;
  try {
    response = await fetch(path, { ...options, headers });
  } catch (_) {
    throw new Error('本机表单服务已停止或不可访问。');
  }
  let payload = {};
  try {
    payload = await response.json();
  } catch (_) {
    payload = {};
  }
  if (!response.ok || payload.success === false) {
    const error = new Error(payload.message || '当前操作未完成，请检查后重试。');
    error.httpStatus = response.status;
    throw error;
  }
  return payload;
}

function post(path, value, options = {}) {
  return requestApi(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
    ...options,
  });
}

function notifyHost(type) {
  if (window.parent === window) return;
  window.parent.postMessage({ type }, '*');
}

function fileFromUploadItem(item) {
  return item && (item.originFile || item);
}

function formatSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function formatSendTime(preview) {
  if (!preview.scheduled) return '确认后立即发送';
  return `${new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    dateStyle: 'medium',
    timeStyle: 'short',
    hour12: false,
  }).format(new Date(preview.sendTime * 1000))}（北京时间）`;
}

function formatTestTime(value) {
  if (value === null || value === undefined || value === '') return '--';
  const numeric = Number(value);
  const date = Number.isFinite(numeric)
    ? new Date(numeric < 1000000000000 ? numeric * 1000 : numeric)
    : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(date);
}

function formatTestStatus(value) {
  const labels = {
    1: '已发送，等待回执',
    2: '发送失败',
    3: '已收到成功回执',
  };
  return labels[value] || '未知';
}

function useCompact() {
  const [compact, setCompact] = useState(
    () => window.matchMedia('(max-width: 760px)').matches,
  );
  useEffect(() => {
    const query = window.matchMedia('(max-width: 760px)');
    const update = () => setCompact(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return compact;
}

function SectionHeading({ title, description }) {
  return (
    <div className="batch-section-heading">
      <h2>{title}</h2>
      {description && <p>{description}</p>}
    </div>
  );
}

function Completion({ result }) {
  let status = 'info';
  let title = '本次创建已结束';
  let subTitle = '请回到对话查看当前流程状态。';
  if (result.status === 'batch_task_confirmed') {
    status = 'success';
    title = '群发任务已创建并确认';
    subTitle = `任务 ID：${result.taskId}；有效号码 ${result.totalCount} 个，重复 ${result.dupCount} 条。`;
  } else if (result.status === 'batch_confirmation_failed') {
    status = 'error';
    title = '任务已创建，但未能确认发送';
    subTitle = `任务 ID：${result.taskId}。请核对该任务，不要重新创建。`;
  } else if (result.status === 'batch_confirmation_outcome_unknown') {
    status = 'warning';
    title = '任务确认结果暂时无法确定';
    subTitle = `任务 ID：${result.taskId}。请查询同一任务，不要重复创建或确认。`;
  } else if (result.status === 'batch_creation_outcome_unknown') {
    status = 'warning';
    title = '任务创建结果暂时无法确定';
    subTitle = '请核对原任务，不要换一种方式重新提交。';
  } else if (result.status === 'batch_creation_failed') {
    status = 'error';
    title = '任务创建未完成';
    subTitle = `错误码：${result.code || '未知'}。请回到对话处理当前错误。`;
  } else if (result.status === 'batch_file_validated') {
    title = '预览已结束，任务尚未启动';
    subTitle = `任务 ID：${result.taskId}。文件已校验，关闭页面不会取消任务。需要取消时，请回到对话提出。`;
  } else if (result.status === 'batch_form_closed') {
    title = '已放弃本次创建';
    subTitle = '本机文件草稿已清除。';
  }
  return (
    <main className="batch-result-page">
      <Result status={status} title={title} subTitle={subTitle} />
    </main>
  );
}

function App() {
  const compact = useCompact();
  const [metadata, setMetadata] = useState(null);
  const [fileList, setFileList] = useState([]);
  const [fileInfo, setFileInfo] = useState(null);
  const [scheduled, setScheduled] = useState(true);
  const [sendTime, setSendTime] = useState('');
  const [sendTimeTouched, setSendTimeTouched] = useState(false);
  const [preview, setPreview] = useState(null);
  const [validationError, setValidationError] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [testPhone, setTestPhone] = useState('');
  const [testParams, setTestParams] = useState({});
  const [testResult, setTestResult] = useState(null);
  const [testDelivery, setTestDelivery] = useState(null);
  const [testStatusError, setTestStatusError] = useState('');
  const [testStatusLoading, setTestStatusLoading] = useState(false);
  const [testSendLocked, setTestSendLocked] = useState(false);
  const [loadingAction, setLoadingAction] = useState('');
  const [result, setResult] = useState(null);
  const [bootError, setBootError] = useState('');
  const active = useRef(true);
  const uploadedUid = useRef('');
  const automaticValidationKey = useRef('');
  const testStatusRequest = useRef(0);

  const busy = Boolean(loadingAction);
  const sendTimeMissing = scheduled && !sendTime;
  const showSendTimeError = sendTimeMissing
    && (sendTimeTouched || Boolean(fileInfo));

  const invalidatePreview = () => {
    setValidationError('');
    setPreview(null);
    setConfirmed(false);
  };

  const resetTestStatus = () => {
    testStatusRequest.current += 1;
    setTestResult(null);
    setTestDelivery(null);
    setTestStatusError('');
    setTestStatusLoading(false);
  };

  const run = async (name, action) => {
    setLoadingAction(name);
    try {
      return await action();
    } catch (error) {
      Message.error(error.message || '操作失败，请稍后重试。');
      throw error;
    } finally {
      setLoadingAction('');
    }
  };

  const downloadTemplate = async () => {
    await run('download', async () => {
      const response = await fetch('/api/template', {
        headers: { 'X-Batch-Context': token },
      });
      if (!response.ok) {
        let detail = {};
        try {
          detail = await response.json();
        } catch (_) {
          // Use the stable fallback below.
        }
        throw new Error(detail.message || '名单模板下载失败，请稍后重试。');
      }
      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition') || '';
      const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      const fileName = encoded
        ? decodeURIComponent(encoded[1])
        : 'recipients.csv';
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      Message.success('名单模板已下载');
    });
  };

  const selectFile = async (item) => {
    const file = fileFromUploadItem(item);
    if (!file || item.uid === uploadedUid.current) return;
    invalidatePreview();
    setFileInfo(null);
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setFileList([]);
      Message.error('请选择 CSV 文件');
      return;
    }
    if (!file.size || file.size > metadata.maxFileBytes) {
      setFileList([]);
      Message.error('文件不能为空，且不能超过 50 MB');
      return;
    }
    uploadedUid.current = item.uid;
    try {
      await run('file', async () => {
        const response = await requestApi('/api/file', {
          method: 'POST',
          headers: { 'Content-Type': 'text/csv' },
          body: file,
        });
        setFileInfo({ ...response.file, revision: response.revision });
        setFileList([{ ...item, status: 'done' }]);
        Message.success('文件上传成功，将自动校验');
      });
    } catch (_) {
      uploadedUid.current = '';
      setFileList([]);
    }
  };

  const removeFile = async () => {
    try {
      await run('file', async () => {
        await post('/api/file/clear', {});
        uploadedUid.current = '';
        setFileList([]);
        setFileInfo(null);
        invalidatePreview();
      });
      return true;
    } catch (_) {
      return false;
    }
  };

  const refreshTestSmsStatus = async (messageId, retry = false) => {
    if (!messageId) return;
    const requestId = testStatusRequest.current + 1;
    testStatusRequest.current = requestId;
    setTestStatusLoading(true);
    setTestStatusError('');
    const attempts = retry ? 5 : 1;
    try {
      for (let index = 0; index < attempts; index += 1) {
        const response = await post('/api/test-send/status', { messageId });
        if (testStatusRequest.current !== requestId) return;
        setTestDelivery(response.status);
        if (response.status.found) return;
        if (index + 1 < attempts) {
          await new Promise((resolve) => window.setTimeout(resolve, 500));
        }
      }
    } catch (error) {
      if (testStatusRequest.current === requestId) {
        setTestStatusError(error.message || '发送结果查询失败，请稍后刷新。');
      }
    } finally {
      if (testStatusRequest.current === requestId) {
        setTestStatusLoading(false);
      }
    }
  };

  const sendTestSms = async () => {
    resetTestStatus();
    await run('test-send', async () => {
      const response = await post('/api/test-send', {
        phone: testPhone,
        templateParams: testParams,
      });
      setTestResult(response.result);
      if (response.result.outcomeUnknown) {
        setTestSendLocked(true);
        Message.warning('测试短信结果暂时无法确定，请勿重复发送');
      } else {
        Message.success('测试短信已提交');
        const messageId = response.result.messageId
          || response.result.messageIds?.[0];
        if (messageId) {
          refreshTestSmsStatus(messageId, true);
        }
      }
    });
  };

  const createAndConfirm = async () => {
    if (!preview || !confirmed) return;
    try {
      await run('create', async () => {
        const response = await post('/api/create', {
          revision: preview.revision,
          confirmed: true,
        });
        setResult(response.result);
        notifyHost('batch:wizard-finished');
      });
    } catch (error) {
      if (error.httpStatus === 400) {
        invalidatePreview();
        return;
      }
      setResult({ status: 'batch_creation_outcome_unknown' });
      notifyHost('batch:wizard-finished');
    }
  };

  const abandon = async () => {
    await run('abandon', async () => {
      const response = await post('/api/abandon', {});
      setResult(response.result);
      notifyHost('batch:wizard-finished');
    });
  };

  useEffect(() => {
    let heartbeat;
    const markActive = () => {
      active.current = true;
    };
    ['pointerdown', 'keydown', 'change'].forEach((name) =>
      document.addEventListener(name, markActive, { passive: true }),
    );
    const detach = () => {
      if (!token) return;
      post('/api/detach', {}, { keepalive: true }).catch(() => {});
    };
    window.addEventListener('pagehide', detach);
    (async () => {
      try {
        const response = await requestApi('/api/state');
        const state = response.state;
        setMetadata(state);
        setScheduled(state.scheduled !== false);
        setSendTime(
          state.sendTime ? String(state.sendTime).replace('T', ' ') : '',
        );
        setTestParams(
          Object.fromEntries(
            (state.templateVariables || []).map((name) => [name, '']),
          ),
        );
        await post('/api/heartbeat', { active: true });
        notifyHost('batch:wizard-ready');
        heartbeat = window.setInterval(() => {
          const recentActivity = active.current;
          active.current = false;
          post('/api/heartbeat', { active: recentActivity }).catch(() => {
            window.clearInterval(heartbeat);
            setBootError('本机表单服务已结束或连接中断。');
          });
        }, 10000);
      } catch (error) {
        setBootError(error.message || '无法加载本机表单。');
      }
    })();
    return () => {
      if (heartbeat) window.clearInterval(heartbeat);
      window.removeEventListener('pagehide', detach);
      ['pointerdown', 'keydown', 'change'].forEach((name) =>
        document.removeEventListener(name, markActive),
      );
    };
  }, []);

  useEffect(() => {
    if (
      !metadata
      || !fileInfo
      || result
      || loadingAction
      || (scheduled && !sendTime)
    ) {
      return undefined;
    }
    const validationKey = [
      fileInfo.revision,
      fileInfo.fileSha256,
      scheduled ? 'scheduled' : 'immediate',
      scheduled ? sendTime : '',
    ].join(':');
    if (automaticValidationKey.current === validationKey) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      automaticValidationKey.current = validationKey;
      setValidationError('');
      run('preview', async () => {
        const response = await post('/api/preview', {
          scheduled,
          sendTime: scheduled ? `${sendTime}:00+08:00` : null,
        });
        if (response.result) {
          setResult(response.result);
          notifyHost('batch:wizard-finished');
          return;
        }
        if (automaticValidationKey.current !== validationKey) return;
        setPreview(response.preview);
        setConfirmed(false);
        Message.success('短信服务校验完成');
        window.setTimeout(() => {
          document
            .getElementById('batch-validation-result')
            ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 0);
      }).catch((error) => {
        setValidationError(error.message || '校验未完成，请检查当前文件和发送时间。');
      });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [metadata, fileInfo, scheduled, sendTime, loadingAction, result]);

  if (result) return <Completion result={result} />;
  if (bootError) {
    return (
      <main className="batch-boot-error">
        <Alert
          type="error"
          showIcon
          title="群发表单加载失败"
          content={bootError}
        />
      </main>
    );
  }
  if (!metadata) {
    return (
      <main className="batch-loading">
        <Spin dot tip="正在加载群发任务…" />
      </main>
    );
  }
  const taskDetails = [
    { label: '任务名称', value: metadata.taskName },
    { label: '消息组', value: metadata.subAccount },
    { label: '短信签名', value: metadata.signature },
    ...(metadata.templateId
      ? [{ label: '模板 ID', value: metadata.templateId }]
      : []),
  ];

  return (
    <div className="batch-page">
      <header className="batch-header">
        <div className="batch-header-inner">
          <div className="batch-title-row">
            <div>
              <div className="batch-brand">火山引擎短信</div>
              <h1>创建群发任务</h1>
              <p>核对短信信息、上传收件人名单并确认启动发送。</p>
            </div>
            <Button
              status="danger"
              icon={<IconClose />}
              loading={loadingAction === 'abandon'}
              disabled={busy}
              onClick={abandon}
            >
              结束预览
            </Button>
          </div>
          <Alert
            className="batch-privacy"
            type="success"
            showIcon
            content="手机号和逐行变量仅由本机页面传给短信服务，不会作为工具结果进入对话。完成前请保持本页面打开。"
          />
        </div>
      </header>

      <main className="batch-body">
        <section className="batch-sheet">
          {busy && loadingAction !== 'download' && (
            <div className="batch-working">
              <Spin dot />
              <span>
                {loadingAction === 'preview'
                  ? '短信服务正在校验文件'
                  : loadingAction === 'create'
                    ? '正在创建并确认任务'
                    : loadingAction === 'test-send'
                      ? '正在发送测试短信'
                      : '正在处理'}
              </span>
            </div>
          )}

          <section className="batch-section">
            <SectionHeading
              title="任务信息"
              description="以下信息由已确认的短信资源生成，仅支持查看。"
            />
            <Descriptions
              border
              column={compact ? 1 : 2}
              data={taskDetails}
            />
            <div className="batch-content-block">
              <div className="batch-field-label">
                短信内容
              </div>
              <div className="batch-message-content">{metadata.content}</div>
              {metadata.description && <p>{metadata.description}</p>}
            </div>
          </section>

          <section className="batch-section">
            <SectionHeading title="上传文件" />
            <div className="batch-upload-actions">
              <Button
                icon={<IconDownload />}
                loading={loadingAction === 'download'}
                disabled={busy}
                onClick={downloadTemplate}
              >
                点击下载模板
              </Button>
              <Upload
                className="batch-upload-button"
                accept=".csv,text/csv"
                autoUpload={false}
                disabled={busy}
                fileList={fileList}
                limit={{ maxCount: 1, hideOnExceedLimit: true }}
                onChange={(nextList) => {
                  const latest = nextList.slice(-1);
                  setFileList(latest);
                  if (latest[0]) selectFile(latest[0]);
                }}
                onRemove={removeFile}
                onExceedLimit={() => Message.warning('只能选择一个名单文件')}
              >
                <Button
                  type="primary"
                  icon={<IconUpload />}
                  loading={loadingAction === 'file'}
                >
                  点击上传文件
                </Button>
              </Upload>
            </div>
            <ol className="batch-upload-notes">
              <li>请先下载模板，填写对应变量后上传文件。注意请勿修改表格第一行！</li>
              <li>群发任务文件最多支持上传 100 万条手机号</li>
              <li>请上传 .csv 格式文件，大小为 50MB 以内</li>
            </ol>
            {fileInfo && (
              <Alert
                className="batch-file-ready"
                type="success"
                showIcon
                content={`文件已就绪，大小 ${formatSize(fileInfo.fileSize)}`}
              />
            )}
          </section>

          <section className="batch-section">
            <SectionHeading title="发送时间" />
            <div className="batch-form-field">
              <div className="batch-field-label">是否定时</div>
              <Radio.Group
                value={scheduled ? 'scheduled' : 'immediate'}
                disabled={busy}
                onChange={(value) => {
                  setScheduled(value === 'scheduled');
                  invalidatePreview();
                }}
              >
                <Radio value="immediate">否</Radio>
                <Radio value="scheduled">是</Radio>
              </Radio.Group>
            </div>
            {scheduled && (
              <div className="batch-form-field">
                <div className="batch-field-label required">定时时间</div>
                <DatePicker
                  showTime
                  format="YYYY-MM-DD HH:mm"
                  value={sendTime || undefined}
                  disabled={busy}
                  error={showSendTimeError}
                  placeholder="请选择日期"
                  onChange={(value) => {
                    setSendTimeTouched(true);
                    setSendTime(value || '');
                    invalidatePreview();
                  }}
                  onBlur={() => setSendTimeTouched(true)}
                />
                {showSendTimeError && (
                  <div className="batch-field-error">请选择定时时间</div>
                )}
                <div className="batch-field-help">
                  定时发送须在未来一个月内，国内消息发送时段为每天
                  08:00–21:30。
                </div>
              </div>
            )}
          </section>

          {metadata.testSendSupported && (
            <section className="batch-section">
              <SectionHeading
                title="发送测试短信"
                description="可发送一条测试短信确认签名、模板和变量替换后的触达效果。"
              />
              <div className="batch-test-phone">
                <div className="batch-field-label">测试手机号</div>
                <div className="batch-inline-control">
                  <Input
                    value={testPhone}
                    disabled={busy}
                    maxLength={20}
                    placeholder="请输入中国大陆手机号"
                    onChange={(value) => {
                      setTestPhone(value);
                      resetTestStatus();
                    }}
                  />
                  <Button
                    loading={loadingAction === 'test-send'}
                    disabled={busy || !testPhone || testSendLocked}
                    onClick={sendTestSms}
                  >
                    发送测试短信
                  </Button>
                </div>
              </div>
              <div className="batch-test-params">
                <div className="batch-field-label">测试所需参数</div>
                {metadata.templateVariables.length === 0 ? (
                  <div className="batch-none">无</div>
                ) : (
                  <div className="batch-param-grid">
                    {metadata.templateVariables.map((name) => (
                      <label key={name}>
                        <span>{name}</span>
                        <Input
                          value={testParams[name] || ''}
                          disabled={busy}
                          placeholder={`请输入 ${name}`}
                          onChange={(value) => {
                            setTestParams((current) => ({
                              ...current,
                              [name]: value,
                            }));
                            resetTestStatus();
                          }}
                        />
                      </label>
                    ))}
                  </div>
                )}
              </div>
              {testResult && (
                <Alert
                  className="batch-test-result"
                  type={testResult.outcomeUnknown ? 'warning' : 'success'}
                  showIcon
                  content={
                    testResult.outcomeUnknown
                      ? '测试短信结果暂时无法确定，请勿重复发送。'
                      : '测试短信已提交，请在测试手机上确认触达效果。'
                  }
                />
              )}
              {testResult && !testResult.outcomeUnknown && (
                <div className="batch-test-log">
                  <div className="batch-test-log-header">
                    <div>
                      <div className="batch-field-label">发送结果</div>
                      <div className="batch-field-help">
                        提交后自动查询；运营商回执可能稍后到达。
                      </div>
                    </div>
                    <Button
                      type="text"
                      icon={<IconRefresh />}
                      loading={testStatusLoading}
                      disabled={testStatusLoading}
                      onClick={() =>
                        refreshTestSmsStatus(
                          testResult.messageId || testResult.messageIds?.[0],
                        )
                      }
                    >
                      刷新发送结果
                    </Button>
                  </div>
                  {testStatusError ? (
                    <Alert type="error" showIcon content={testStatusError} />
                  ) : (
                    <Spin loading={testStatusLoading}>
                      {testDelivery?.found ? (
                        <Descriptions
                          border
                          column={compact ? 1 : 2}
                          data={[
                            {
                              label: 'Message ID',
                              value: testDelivery.messageId,
                            },
                            {
                              label: '发送状态',
                              value: formatTestStatus(testDelivery.status),
                            },
                            {
                              label: '发送时间',
                              value: formatTestTime(testDelivery.sendTime),
                            },
                            {
                              label: '回执时间',
                              value: formatTestTime(testDelivery.receiptTime),
                            },
                            {
                              label: '计费条数',
                              value: testDelivery.count ?? '--',
                            },
                            {
                              label: '错误码',
                              value: testDelivery.errorCode || '--',
                            },
                            {
                              label: '错误信息',
                              value: testDelivery.errorMessage || '--',
                            },
                          ]}
                        />
                      ) : (
                        <Alert
                          type="info"
                          showIcon
                          content="暂未查询到发送结果，可稍后刷新。"
                        />
                      )}
                    </Spin>
                  )}
                </div>
              )}
            </section>
          )}

          <section className="batch-section">
            <SectionHeading
              title="校验结果与确认"
              description="文件上传且发送时间有效后，短信服务会自动校验；请核对统计并确认启动任务。"
            />
            {validationError ? (
              <Alert type="error" showIcon title="校验未完成" content={validationError} />
            ) : !preview ? (
              <Alert
                type="info"
                showIcon
                content={
                  !fileInfo
                    ? '上传名单文件后将自动校验。'
                    : scheduled && !sendTime
                      ? '请选择定时时间，设置完成后将自动校验。'
                      : '短信服务正在自动校验文件。'
                }
              />
            ) : (
              <div id="batch-validation-result">
                <div className="batch-counts">
                  <div><span>有效号码</span><strong>{preview.totalCount}</strong></div>
                  <div><span>重复数据</span><strong>{preview.dupCount}</strong></div>
                </div>
                <Descriptions
                  className="batch-confirm-details"
                  border
                  column={compact ? 1 : 2}
                  data={[
                    { label: '任务名称', value: metadata.taskName },
                    { label: '短信签名', value: metadata.signature },
                    ...(metadata.templateId
                      ? [{ label: '模板 ID', value: metadata.templateId }]
                      : []),
                    { label: '发送安排', value: formatSendTime(preview) },
                  ]}
                />
                {preview.dupCount > 0 && (
                  <Alert
                    className="batch-validation-warning"
                    type="warning"
                    showIcon
                    content="重复号码已由服务端去重，请核对有效号码数后继续。"
                  />
                )}
                <div className="batch-confirm">
                  <Checkbox
                    checked={confirmed}
                    disabled={busy}
                    onChange={setConfirmed}
                  >
                    我已核对任务信息、文件校验结果和发送时间，确认启动该群发任务
                  </Checkbox>
                </div>
              </div>
            )}
          </section>

          <footer className="batch-actions">
            <Button
              status="danger"
              disabled={busy}
              onClick={abandon}
            >
              结束预览
            </Button>
            <div>
              <Button
                type="primary"
                icon={<IconCheck />}
                loading={loadingAction === 'create'}
                disabled={busy || !preview || !confirmed}
                onClick={createAndConfirm}
              >
                确认并启动任务
              </Button>
            </div>
          </footer>
        </section>
      </main>
    </div>
  );
}

class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="batch-boot-error">
        <Alert
          type="error"
          showIcon
          title="群发表单加载失败"
          content="请关闭当前页面，并从群发任务入口重新打开。"
        />
      </main>
    );
  }
}

ReactDOM.createRoot(rootElement).render(
  <AppErrorBoundary>
    <App />
  </AppErrorBoundary>,
);
