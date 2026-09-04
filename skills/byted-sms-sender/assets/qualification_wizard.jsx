/* global React, ReactDOM, arco, arcoicon */
// Build with esbuild: --loader:.jsx=jsx --target=es2019 --format=iife --minify.

const {
  Alert,
  Button,
  Checkbox,
  DatePicker,
  Descriptions,
  Form,
  Input,
  Message,
  Modal,
  Radio,
  Result,
  Select,
  Spin,
  Steps,
  Tag,
  Upload,
  VerificationCode,
} = arco;
const { RangePicker } = DatePicker;
const {
  IconCheck,
  IconClose,
  IconExclamationCircle,
  IconLeft,
  IconRight,
  IconUpload,
} = arcoicon;
const { useCallback, useEffect, useMemo, useRef, useState } = React;

const rootElement = document.getElementById('qualification-root');
const token = window.location.hash.slice(1);
if (token) {
  try {
    window.history.replaceState(
      null,
      '',
      window.location.pathname + window.location.search,
    );
  } catch (_) {
    // Some embedded WebViews disallow history mutation; fragments still stay local.
  }
}
const maxBytes = Number(rootElement.dataset.maxImageBytes);
const imageAccept = '.jpg,.jpeg,.png,image/jpeg,image/png';
const roles = {
  legal: { title: '法人信息', shortTitle: '法人' },
  operator: { title: '经办人信息', shortTitle: '经办人' },
  responsible: { title: '责任人信息', shortTitle: '责任人' },
};
const allStepKeys = [
  'base',
  'business',
  'legal',
  'operator',
  'responsible',
  'authorization',
  'review',
];
const stepTitles = {
  base: '基础信息',
  business: '企业信息',
  legal: '法人信息',
  operator: '经办人信息',
  responsible: '责任人信息',
  authorization: '授权材料',
  review: '确认提交',
};

function supportMessage(payload, fallback) {
  const error = (payload && payload.error) || {};
  const reference =
    error.logId || error.requestId || (payload && (payload.logId || payload.requestId));
  return `${(payload && payload.message) || fallback}${
    reference ? `（排障编号：${reference}）` : ''
  }`;
}

async function requestApi(path, options = {}) {
  if (!token) {
    throw new Error('本地预览链接无效，请重新打开最新预览链接。');
  }
  const headers = new Headers(options.headers || {});
  headers.set('X-Qualification-Context', token);
  let response;
  try {
    response = await fetch(path, { ...options, headers });
  } catch (_) {
    throw new Error(
      '本地预览服务已停止或不可访问，请重新打开最新预览链接。',
    );
  }
  let payload = {};
  try {
    payload = await response.json();
  } catch (_) {
    payload = {};
  }
  if (!response.ok || payload.success === false) {
    const error = new Error(supportMessage(payload, '操作失败，请稍后重试'));
    error.outcomeUnknown = Boolean(
      payload.outcomeUnknown || (payload.error && payload.error.outcomeUnknown),
    );
    throw error;
  }
  return payload;
}

function notifyHost(status) {
  if (window.parent === window) return;
  window.parent.postMessage(
    { type: 'qualification:wizard-finished', status },
    '*',
  );
}

function notifyHostReady() {
  if (window.parent === window) return;
  window.parent.postMessage({ type: 'qualification:wizard-ready' }, '*');
}

function normalizeDate(value) {
  const match = String(value || '').match(
    /^(\d{4})[^0-9]?(\d{1,2})[^0-9]?(\d{1,2})/,
  );
  return match
    ? `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`
    : '';
}

function fileFromUploadItem(item) {
  return item && (item.originFile || item);
}

function uploadItemName(item) {
  const file = fileFromUploadItem(item);
  return (item && item.name) || (file && file.name) || '已选择图片';
}

function validateImageFile(file) {
  if (!file) throw new Error('请选择图片');
  if (file.size > maxBytes) throw new Error('单张图片不能大于 2 MB');
  if (!/\.(jpe?g|png)$/i.test(file.name)) {
    throw new Error('仅支持 JPG、JPEG、PNG 图片');
  }
}

function revokeLocalPreview(item) {
  if (item && item.__localPreviewUrl && typeof URL !== 'undefined') {
    URL.revokeObjectURL(item.__localPreviewUrl);
  }
}

function withLocalPreview(item, enabled) {
  if (!enabled) return item;
  const file = fileFromUploadItem(item);
  if (!file) return item;
  if (item && (item.url || item.thumbUrl)) {
    return { ...item, status: 'done' };
  }
  if (typeof URL === 'undefined') return { ...item, status: 'done' };
  const localPreviewUrl = URL.createObjectURL(file);
  return {
    ...item,
    status: 'done',
    url: localPreviewUrl,
    thumbUrl: localPreviewUrl,
    __localPreviewUrl: localPreviewUrl,
  };
}

async function validateForm(form, requiredFields = []) {
  try {
    await form.validate();
  } catch (_) {
    throw new Error('请检查当前页面中的必填项和格式');
  }
  const values = form.getFieldsValue();
  const missingField = requiredFields.find(
    (field) => !String(values[field] || '').trim(),
  );
  if (missingField) {
    throw new Error('请检查当前页面中的必填项和格式');
  }
  return values;
}

function statusForCheck(target, state) {
  const check = state.checks[target];
  const saved =
    target === 'business' ? state.businessSaved : state.sections[target];
  if (!saved) return { type: 'info', text: '请填写并确认本页信息。' };
  if (!check.attempted) {
    return { type: 'info', text: '信息已保存，等待校验。' };
  }
  if (target === 'business' && !check.matched) {
    return {
      type: 'warning',
      text: '自动校验未通过，将转人工审核；你仍可继续。',
    };
  }
  return check.matched
    ? { type: 'success', text: '信息已保存并校验通过。' }
    : { type: 'error', text: '校验未通过，请核对本页信息后重试。' };
}

function requiredSteps(state, purpose) {
  return allStepKeys.filter(
    (step) => step !== 'authorization' || Number(purpose || state.purpose) === 2,
  );
}

function mobileVerificationDone(role, state) {
  const person = ((state.savedData || {}).people || {})[role] || {};
  return Boolean(
    !state.mobileVerificationRequired ||
      !person.personMobile ||
      (state.mobileVerifications || {})[role],
  );
}

function stepDone(step, state) {
  if (step === 'base') return Boolean(state.baseSaved);
  if (step === 'business') {
    return Boolean(state.businessSaved && state.checks.business.canContinue);
  }
  if (step === 'legal') {
    return Boolean(
      state.legalAcknowledged &&
        (!state.legalCheckRequired || state.checks.legal.matched),
    );
  }
  if (step === 'operator') {
    return Boolean(
      state.sections.operator &&
        state.checks.operator.matched &&
        mobileVerificationDone('operator', state),
    );
  }
  if (step === 'responsible') {
    return Boolean(
      state.sections.responsible &&
        state.checks.responsible.matched &&
        mobileVerificationDone('responsible', state),
    );
  }
  if (step === 'authorization') {
    return (
      Number(state.purpose) !== 2 ||
      Boolean(
        state.authorizationAcknowledged &&
          (!state.powerOfAttorneyRequired || state.powerOfAttorneySaved),
      )
    );
  }
  return false;
}

function nextStep(state) {
  if (!state.baseSaved) return 'base';
  if (!state.businessSaved || !state.checks.business.canContinue) {
    return 'business';
  }
  if (
    !state.legalAcknowledged ||
    (state.legalCheckRequired && !state.checks.legal.matched)
  ) {
    return 'legal';
  }
  if (
    !state.sections.operator ||
    !state.checks.operator.matched ||
    !mobileVerificationDone('operator', state)
  ) {
    return 'operator';
  }
  if (state.sameOperator === null || state.sameOperator === undefined) {
    return 'responsible';
  }
  if (
    !state.sections.responsible ||
    !state.checks.responsible.matched ||
    !mobileVerificationDone('responsible', state)
  ) {
    return 'responsible';
  }
  if (
    Number(state.purpose) === 2 &&
    (!state.authorizationAcknowledged ||
      (state.powerOfAttorneyRequired && !state.powerOfAttorneySaved))
  ) {
    return 'authorization';
  }
  return 'review';
}

function useCompactLayout() {
  const [compact, setCompact] = useState(() => window.innerWidth <= 820);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 820px)');
    const update = () => setCompact(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return compact;
}

function StepHeader({ title, description, status }) {
  const statusColor =
    status === 'done' ? 'green' : status === 'optional' ? 'gray' : 'arcoblue';
  const statusText =
    status === 'done' ? '已完成' : status === 'optional' ? '选填' : '填写中';
  return (
    <>
      <div className="step-heading">
        <h2>{title}</h2>
        <Tag color={statusColor}>{statusText}</Tag>
      </div>
      <p className="step-description">{description}</p>
    </>
  );
}

function StepStatus({ status }) {
  if (!status || !status.text) return null;
  return (
    <Alert
      className="step-status"
      type={status.type || 'info'}
      showIcon
      content={status.text}
    />
  );
}

function FilePicker({
  fileKey,
  title,
  tip = '支持 JPG、JPEG、PNG，单张不大于 2 MB',
  required = false,
  files,
  setFiles,
  markChanged,
  onSelectionChange,
  onFileSelected,
  disabled = false,
  compact = false,
  rectangular = false,
  maxCount = 1,
  uploadTitle = '',
}) {
  const fileList = files[fileKey] || [];
  const firstFile = fileList[0];
  const previewUrl = firstFile && (firstFile.url || firstFile.thumbUrl);
  const visualMode = compact || rectangular;
  const clearFiles = () => {
    setFiles((current) => {
      (current[fileKey] || []).forEach(revokeLocalPreview);
      return { ...current, [fileKey]: [] };
    });
    markChanged();
    if (onSelectionChange) onSelectionChange();
  };
  return (
    <div
      className={`upload-block${visualMode ? ' upload-block-compact' : ''}${
        rectangular ? ' upload-block-rectangle' : ''
      }`}
    >
      <span
        className={`upload-label${required ? ' upload-label-required' : ''}`}
      >
        {title}
      </span>
      <Upload
        className={`upload-zone${visualMode ? ' upload-zone-compact' : ''}${
          rectangular ? ' upload-zone-rectangle' : ''
        }`}
        accept={imageAccept}
        autoUpload={false}
        disabled={disabled}
        drag={!visualMode}
        fileList={fileList}
        listType={visualMode ? 'picture-card' : 'text'}
        limit={{ maxCount, hideOnExceedLimit: !rectangular }}
        onChange={(nextList) => {
          let latest = nextList.slice(-maxCount);
          try {
            latest.forEach((item) => validateImageFile(fileFromUploadItem(item)));
          } catch (error) {
            Message.error(error.message);
            return;
          }
          latest = latest.map((item) => withLocalPreview(item, visualMode));
          setFiles((current) => {
            const previous = current[fileKey] || [];
            const nextUids = new Set(latest.map((item) => item.uid));
            previous.forEach((item) => {
              if (!nextUids.has(item.uid)) revokeLocalPreview(item);
            });
            return { ...current, [fileKey]: latest };
          });
          markChanged();
          if (onSelectionChange) onSelectionChange();
          if (latest[0] && onFileSelected) {
            onFileSelected(fileFromUploadItem(latest[0]));
          }
        }}
        onRemove={() => {
          clearFiles();
          return true;
        }}
        onExceedLimit={() =>
          Message.warning(`此项最多选择 ${maxCount} 张图片`)
        }
        showUploadList={!rectangular}
      >
        <div
          className={
            rectangular
              ? `upload-rectangle-trigger${firstFile ? ' has-file' : ''}`
              : compact
                ? 'upload-picture-trigger'
                : ''
          }
        >
          {rectangular && firstFile ? (
            <>
              {previewUrl ? (
                <img src={previewUrl} alt={title} />
              ) : (
                <IconUpload className="upload-icon" />
              )}
              <div className="upload-rectangle-mask">
                <IconUpload />
                <span>重新上传</span>
              </div>
              <div className="upload-rectangle-name" title={uploadItemName(firstFile)}>
                {uploadItemName(firstFile)}
              </div>
              <button
                type="button"
                className="upload-rectangle-remove"
                title="移除文件"
                aria-label={`移除${title}`}
                onMouseDown={(event) => event.stopPropagation()}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  clearFiles();
                }}
              >
                <IconClose />
              </button>
            </>
          ) : (
            <>
              <IconUpload className="upload-icon" />
              <div className="upload-title">
                {uploadTitle || '点击或拖拽图片到这里'}
              </div>
            </>
          )}
        </div>
      </Upload>
      {tip && <div className="upload-tip">{tip}</div>}
    </div>
  );
}

function App() {
  const compact = useCompactLayout();
  const [baseForm] = Form.useForm();
  const [legalForm] = Form.useForm();
  const [operatorForm] = Form.useForm();
  const [responsibleForm] = Form.useForm();
  const forms = {
    base: baseForm,
    legal: legalForm,
    operator: operatorForm,
    responsible: responsibleForm,
  };

  const [state, setState] = useState(null);
  const [activeStep, setActiveStep] = useState('base');
  const [purpose, setPurpose] = useState(1);
  const [businessCertificateType, setBusinessCertificateType] = useState(1);
  const [legalCertificateType, setLegalCertificateType] = useState(undefined);
  const [businessValues, setBusinessValues] = useState({
    businessCertificateName: '',
    unifiedSocialCreditIdentifier: '',
    businessCertificateValidityPeriod: [],
    legalPersonName: '',
  });
  const [personValues, setPersonValues] = useState({
    operator: { personName: '', personIDCard: '', personMobile: '' },
    responsible: { personName: '', personIDCard: '', personMobile: '' },
  });
  const [files, setFiles] = useState({});
  const [status, setStatus] = useState({});
  const [pendingBusiness, setPendingBusiness] = useState(false);
  const [showPersonOcr, setShowPersonOcr] = useState({});
  const [fileChanges, setFileChanges] = useState({});
  const [legalName, setLegalName] = useState('');
  const [recognizedLegalName, setRecognizedLegalName] = useState('');
  const [materialNameTouched, setMaterialNameTouched] = useState(false);
  const [ocrCompleted, setOcrCompleted] = useState({});
  const [verificationCodes, setVerificationCodes] = useState({});
  const [verificationCooldowns, setVerificationCooldowns] = useState({});
  const [verificationStatus, setVerificationStatus] = useState({});
  const [loadingAction, setLoadingAction] = useState('');
  const [preview, setPreview] = useState(null);
  const [confirmed, setConfirmed] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [completion, setCompletion] = useState(null);
  const initialized = useRef(false);
  const dirtySteps = useRef(new Set());
  const completionLocked = useRef(false);
  const activitySinceHeartbeat = useRef(true);
  const lifecycleFinished = useRef(false);
  const heartbeatTimer = useRef(null);

  useEffect(() => {
    notifyHostReady();
  }, []);

  const finishLifecycle = useCallback((status) => {
    lifecycleFinished.current = true;
    if (heartbeatTimer.current !== null) {
      window.clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
    notifyHost(status);
  }, []);

  const updateStatus = useCallback((step, text, type = 'info') => {
    setStatus((current) => ({ ...current, [step]: { text, type } }));
  }, []);

  const markChanged = useCallback((step) => {
    if (!completionLocked.current) setHasChanges(true);
    dirtySteps.current.add(step);
  }, []);

  useEffect(() => {
    const beforeUnload = (event) => {
      if (!hasChanges || completionLocked.current) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [hasChanges]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setVerificationCooldowns((current) => {
        let changed = false;
        const next = {};
        Object.entries(current).forEach(([role, seconds]) => {
          const remaining = Math.max(0, Number(seconds) - 1);
          next[role] = remaining;
          if (remaining !== seconds) changed = true;
        });
        return changed ? next : current;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const markActivity = () => {
      activitySinceHeartbeat.current = true;
    };
    const sendHeartbeat = async () => {
      if (lifecycleFinished.current) return;
      const active = activitySinceHeartbeat.current;
      activitySinceHeartbeat.current = false;
      try {
        await requestApi('/api/heartbeat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ active }),
        });
      } catch (_) {
        activitySinceHeartbeat.current =
          activitySinceHeartbeat.current || active;
      }
    };
    const detach = () => {
      if (lifecycleFinished.current) return;
      requestApi('/api/detach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
        keepalive: true,
      }).catch(() => {});
    };
    const activityEvents = ['input', 'change', 'keydown', 'pointerdown'];
    activityEvents.forEach((eventName) => {
      document.addEventListener(eventName, markActivity, true);
    });
    window.addEventListener('pagehide', detach);
    heartbeatTimer.current = window.setInterval(sendHeartbeat, 15000);
    sendHeartbeat();
    return () => {
      activityEvents.forEach((eventName) => {
        document.removeEventListener(eventName, markActivity, true);
      });
      window.removeEventListener('pagehide', detach);
      if (heartbeatTimer.current !== null) {
        window.clearInterval(heartbeatTimer.current);
        heartbeatTimer.current = null;
      }
    };
  }, []);

  const hydrateForms = useCallback(
    (nextState) => {
      const business = (nextState.savedData || {}).business || {};
      const people = (nextState.savedData || {}).people || {};
      baseForm.setFieldsValue({
        purpose: Number(nextState.purpose || 1),
        materialName: nextState.materialName || '',
      });
      setPurpose(Number(nextState.purpose || 1));
      setMaterialNameTouched(nextState.materialNameSource === 'manual');
      setBusinessCertificateType(
        Number(business.businessCertificateType) || 1,
      );
      if (nextState.businessSaved) {
        setBusinessValues({
          businessCertificateName: business.businessCertificateName || '',
          unifiedSocialCreditIdentifier:
            business.unifiedSocialCreditIdentifier || '',
          legalPersonName: business.legalPersonName || '',
          businessCertificateValidityPeriod: [
            business.businessCertificateValidityPeriodStart || '',
            business.businessCertificateValidityPeriodEnd || '',
          ],
        });
        setPendingBusiness(true);
        setLegalName(business.legalPersonName || '');
      }
      for (const role of ['legal', 'operator', 'responsible']) {
        const person = people[role];
        if (!person) continue;
        if (role === 'legal') {
          setLegalCertificateType(
            person.certificateType === undefined || person.certificateType === null
              ? undefined
              : Number(person.certificateType),
          );
        }
        if (role === 'legal') {
          forms[role].setFieldsValue({
            personName: person.personName || '',
            personIDCard: person.personIDCard || '',
            personMobile: person.personMobile || '',
          });
        } else {
          setPersonValues((current) => ({
            ...current,
            [role]: {
              personName: person.personName || '',
              personIDCard: person.personIDCard || '',
              personMobile: person.personMobile || '',
            },
          }));
        }
      }
    },
    [baseForm, legalForm, operatorForm, responsibleForm],
  );

  const refresh = useCallback(
    async (preferredStep = '') => {
      const payload = await requestApi('/api/state');
      const nextState = payload.state;
      setState(nextState);
      if (!initialized.current) {
        hydrateForms(nextState);
        initialized.current = true;
      } else {
        setPurpose(Number(nextState.purpose || 1));
      }
      const target = preferredStep || nextStep(nextState);
      setActiveStep(target);
      if (target === 'review' && nextState.readyForPreview) {
        setPreview(null);
        setConfirmed(false);
      }
      return nextState;
    },
    [hydrateForms],
  );

  useEffect(() => {
    refresh().catch((error) => {
      updateStatus('boot', error.message, 'error');
    });
  }, [refresh, updateStatus]);

  const stepList = useMemo(
    () => (state ? requiredSteps(state, purpose) : allStepKeys),
    [state, purpose],
  );

  const rank = (state && state.rank) || {};
  const businessImageRequired = Boolean(rank.needBusinessCertificateImage);

  const personRequirement = useCallback(
    (role, kind) => {
      const prefix = role === 'operator' ? 'Operator' : 'Responsible';
      if (kind === 'image') return Boolean(rank[`need${prefix}Image`]);
      return Boolean(
        rank[`${role}ThreeElement`] || rank[`need${prefix}Mobile`],
      );
    },
    [rank],
  );

  const fileValue = useCallback(
    (fileKey) => fileFromUploadItem((files[fileKey] || [])[0]),
    [files],
  );

  const removeDirty = (step) => {
    dirtySteps.current.delete(step);
  };

  const showStep = useCallback((step) => {
    setActiveStep(step);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const saveBase = async () => {
    try {
      const values = await validateForm(baseForm, ['purpose', 'materialName']);
      setLoadingAction('base');
      updateStatus('base', '正在保存基础信息…');
      await requestApi('/api/base', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          purpose: Number(values.purpose),
          materialName: String(values.materialName || '').trim(),
        }),
      });
      removeDirty('base');
      setPreview(null);
      await refresh('business');
      updateStatus('base', '基础信息已保存。', 'success');
      return true;
    } catch (error) {
      if (error instanceof Error) {
        updateStatus('base', error.message, 'error');
      }
      return false;
    } finally {
      setLoadingAction('');
    }
  };

  const selectBusinessFile = fileValue('business');

  const runBusinessOcr = async (selectedFile) => {
    const businessFile = selectedFile || selectBusinessFile;
    try {
      validateImageFile(businessFile);
      setLoadingAction('business-ocr');
      updateStatus('business', '正在上传并识别…');
      const payload = await requestApi('/api/business-ocr', {
        method: 'POST',
        headers: {
          'Content-Type': businessFile.type,
          'X-Document-Type': String(businessCertificateType),
        },
        body: businessFile,
      });
      const documentData = payload.document || {};
      const long = /长期|永久/.test(
        String(documentData.businessCertificateValidityPeriodEnd || ''),
      );
      const validityStart = normalizeDate(
        documentData.businessCertificateValidityPeriodStart,
      );
      const validityEnd = long
        ? '2099-12-31'
        : normalizeDate(documentData.businessCertificateValidityPeriodEnd);
      const nextValues = {
        businessCertificateName:
          documentData.businessCertificateName || '',
        unifiedSocialCreditIdentifier:
          documentData.unifiedSocialCreditIdentifier || '',
        legalPersonName: documentData.legalPersonName || '',
        businessCertificateValidityPeriod:
          validityStart && validityEnd ? [validityStart, validityEnd] : [],
      };
      setBusinessValues(nextValues);
      setLegalName(nextValues.legalPersonName);
      if (!materialNameTouched) {
        const defaultName =
          nextValues.businessCertificateName.length <= 20
            ? nextValues.businessCertificateName
            : '';
        baseForm.setFieldValue('materialName', defaultName);
      }
      setPendingBusiness(true);
      setOcrCompleted((current) => ({ ...current, business: true }));
      markChanged('business');
      updateStatus('business', '识别完成，请核对信息。', 'success');
    } catch (error) {
      updateStatus('business', error.message, 'error');
    } finally {
      setLoadingAction('');
    }
  };

  const checkBusiness = async () => {
    if (!pendingBusiness) {
      updateStatus('business', '请先上传营业证件并完成 OCR。', 'error');
      return false;
    }
    if (selectBusinessFile && !ocrCompleted.business) {
      updateStatus(
        'business',
        '已重新选择证件图片，请先上传并识别。',
        'error',
      );
      return false;
    }
    if (
      businessImageRequired &&
      !state.savedData.business.hasImage &&
      !ocrCompleted.business
    ) {
      updateStatus('business', '请先上传营业证件并识别。', 'error');
      return false;
    }
    try {
      const values = businessValues;
      if (
        !String(values.businessCertificateName || '').trim() ||
        !String(values.unifiedSocialCreditIdentifier || '').trim() ||
        !String(values.legalPersonName || '').trim()
      ) {
        updateStatus('business', '请检查当前页面中的必填项和格式', 'error');
        return false;
      }
      const materialName = String(
        baseForm.getFieldValue('materialName') || '',
      ).trim();
      const businessName = String(values.businessCertificateName || '').trim();
      if (!materialName) {
        updateStatus('business', '请先填写资质名称。', 'error');
        showStep('base');
        return false;
      }
      const validityPeriod = values.businessCertificateValidityPeriod;
      if (!Array.isArray(validityPeriod) || validityPeriod.length !== 2) {
        updateStatus('business', '请选择营业证件有效期。', 'error');
        return false;
      }
      setLoadingAction('business');
      updateStatus('business', '正在校验营业证件有效性…');
      const saved = await requestApi('/api/business', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          businessCertificateType,
          businessCertificateName: businessName,
          unifiedSocialCreditIdentifier: String(
            values.unifiedSocialCreditIdentifier || '',
          ).trim(),
          legalPersonName: String(values.legalPersonName || '').trim(),
          businessCertificateValidityPeriodStart:
            validityPeriod[0],
          businessCertificateValidityPeriodEnd: validityPeriod[1],
          materialName,
          materialNameSource: materialNameTouched ? 'manual' : 'auto',
          purpose: Number(baseForm.getFieldValue('purpose') || 1),
        }),
      });
      if (saved.invalidatedLegal) {
        legalForm.resetFields();
        setShowPersonOcr((current) => ({ ...current, legal: false }));
        setRecognizedLegalName('');
        setOcrCompleted((current) => ({ ...current, legal: false }));
        setFiles((current) => ({
          ...current,
          legalFront: [],
          legalBack: [],
        }));
      }
      await requestApi('/api/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: 'business' }),
      });
      removeDirty('business');
      setPreview(null);
      const nextState = await refresh('business');
      setStatus((current) => ({
        ...current,
        business: statusForCheck('business', nextState),
      }));
      return true;
    } catch (error) {
      if (error instanceof Error) {
        updateStatus('business', error.message, 'error');
      }
      return false;
    } finally {
      setLoadingAction('');
    }
  };

  const continueBusiness = () => {
    if (dirtySteps.current.has('business') || !stepDone('business', state)) {
      updateStatus(
        'business',
        '请先完成营业证件有效性校验；校验未通过时仍可继续填写。',
        'warning',
      );
      return false;
    }
    showStep('legal');
    return true;
  };

  const runPersonOcr = async (role, selected = {}) => {
    const front = selected.front || fileValue(`${role}Front`);
    const back = selected.back || fileValue(`${role}Back`);
    try {
      validateImageFile(front);
      validateImageFile(back);
      setLoadingAction(`${role}-ocr`);
      updateStatus(role, '正在上传并识别…');
      await requestApi(`/api/person-image?role=${role}&side=front`, {
        method: 'POST',
        headers: { 'Content-Type': front.type },
        body: front,
      });
      await requestApi(`/api/person-image?role=${role}&side=back`, {
        method: 'POST',
        headers: { 'Content-Type': back.type },
        body: back,
      });
      const payload = await requestApi(`/api/person-ocr?role=${role}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ certificateType: 0 }),
      });
      const recognized = payload.person || {};
      if (role === 'legal') {
        setLegalCertificateType(0);
        forms[role].setFieldsValue({
          personName: legalName || recognized.personName || '',
          personIDCard: recognized.personIDCard || '',
        });
      } else {
        setPersonValues((current) => ({
          ...current,
          [role]: {
            ...current[role],
            personName: recognized.personName || '',
            personIDCard: recognized.personIDCard || '',
          },
        }));
      }
      markChanged(role);
      if (
        role === 'legal' &&
        recognized.personName &&
        legalName &&
        recognized.personName !== legalName
      ) {
        setRecognizedLegalName(recognized.personName);
        updateStatus(
          role,
          '身份证姓名与营业证件中的法人姓名不一致，请核对。',
          'error',
        );
      } else {
        if (role === 'legal') {
          setRecognizedLegalName(recognized.personName || '');
        }
        updateStatus(role, '识别完成，请核对信息。', 'success');
      }
    } catch (error) {
      updateStatus(role, error.message, 'error');
    } finally {
      setLoadingAction('');
    }
  };

  const maybeRunPersonOcr = (role, side, selectedFile) => {
    const front =
      side === 'front' ? selectedFile : fileValue(`${role}Front`);
    const back =
      side === 'back' ? selectedFile : fileValue(`${role}Back`);
    if (!front || !back) return;
    window.setTimeout(() => runPersonOcr(role, { front, back }), 0);
  };

  const legalHasInput = () => {
    const values = legalForm.getFieldsValue();
    return Boolean(
      legalCertificateType !== undefined ||
        String(values.personIDCard || '').trim() ||
        String(values.personMobile || '').trim() ||
        fileValue('legalFront') ||
        fileValue('legalBack') ||
        (files.legalOther || []).length,
    );
  };

  const saveLegal = async () => {
    try {
      const values = await validateForm(legalForm);
      const isLegalIdCard = legalCertificateType === 0;
      const selectedLegalFront = fileValue('legalFront');
      const selectedLegalBack = fileValue('legalBack');
      const selectedIdentityFile =
        isLegalIdCard ? selectedLegalFront || selectedLegalBack : null;
      const hasSelectedIdentityImages = Boolean(
        selectedLegalFront && selectedLegalBack,
      );
      if (selectedIdentityFile && !hasSelectedIdentityImages) {
        updateStatus(
          'legal',
          '请同时上传身份证人像面和国徽面，或移除已选择图片。',
          'error',
        );
        return false;
      }
      if (
        isLegalIdCard &&
        recognizedLegalName &&
        recognizedLegalName !== legalName
      ) {
        updateStatus(
          'legal',
          '身份证姓名与营业证件中的法人姓名不一致，请重新核对。',
          'error',
        );
        return false;
      }
      setLoadingAction('legal');
      updateStatus(
        'legal',
        legalHasInput()
          ? '正在保存法人信息…'
          : '正在确认无需补充法人信息…',
      );
      if (legalCertificateType !== undefined && legalCertificateType !== 0) {
        const otherDocuments = (files.legalOther || [])
          .map(fileFromUploadItem)
          .filter(Boolean);
        for (let index = 0; index < otherDocuments.length; index += 1) {
          const file = otherDocuments[index];
          validateImageFile(file);
          await requestApi(
            `/api/legal-document?index=${index}&certificateType=${legalCertificateType}${
              index === 0 ? '&replace=1' : ''
            }`,
            {
              method: 'POST',
              headers: { 'Content-Type': file.type },
              body: file,
            },
          );
        }
      }
      await requestApi('/api/person', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: 'legal',
          certificateType: legalCertificateType,
          personName: legalName,
          personIDCard: String(values.personIDCard || '').trim(),
          personMobile: String(values.personMobile || '').trim(),
          skipEmpty: !legalHasInput(),
          identityImagesChanged: fileChanges.legalIdentity === true,
          documentsChanged: fileChanges.legalDocuments === true,
          documentCount: (files.legalOther || []).length,
        }),
      });
      const legalCheckRequired = Boolean(
        isLegalIdCard && String(values.personIDCard || '').trim(),
      );
      if (legalCheckRequired) {
        updateStatus('legal', '正在校验法人信息…');
        await requestApi('/api/check', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target: 'legal' }),
        });
      }
      removeDirty('legal');
      setPreview(null);
      setFileChanges((current) => ({
        ...current,
        legalIdentity: false,
        legalDocuments: false,
      }));
      setOcrCompleted((current) => ({ ...current, legal: false }));
      const nextState = await refresh(legalCheckRequired ? 'legal' : 'operator');
      if (legalCheckRequired && !nextState.checks.legal.matched) {
        setStatus((current) => ({
          ...current,
          legal: statusForCheck('legal', nextState),
        }));
        return false;
      }
      if (legalCheckRequired) await refresh('operator');
      return true;
    } catch (error) {
      if (error instanceof Error) {
        updateStatus('legal', error.message, 'error');
      }
      return false;
    } finally {
      setLoadingAction('');
    }
  };

  const savePersonDraft = async (role) => {
    const selectedFront = fileValue(`${role}Front`);
    const selectedBack = fileValue(`${role}Back`);
    const selectedIdentityFile = selectedFront || selectedBack;
    const hasSelectedIdentityImages = Boolean(selectedFront && selectedBack);
    if (selectedIdentityFile && !hasSelectedIdentityImages) {
      updateStatus(
        role,
        '请同时上传身份证人像面和国徽面，或移除已选择图片。',
        'error',
      );
      return false;
    }
    if (
      personRequirement(role, 'image') &&
      !((((state.savedData || {}).people || {})[role] || {}).hasImages) &&
      !ocrCompleted[role] &&
      !hasSelectedIdentityImages
    ) {
      updateStatus(role, '请先上传身份证正反面。', 'error');
      return false;
    }
    try {
      const values = personValues[role] || {};
      if (
        !String(values.personName || '').trim() ||
        !/^[0-9]{17}[0-9Xx]$/.test(String(values.personIDCard || '').trim()) ||
        (personRequirement(role, 'mobile') &&
          !/^1[3-9][0-9]{9}$/.test(String(values.personMobile || '').trim())) ||
        (String(values.personMobile || '').trim() &&
          !/^1[3-9][0-9]{9}$/.test(String(values.personMobile || '').trim()))
      ) {
        updateStatus(role, '请检查当前页面中的必填项和格式', 'error');
        return false;
      }
      setLoadingAction(role);
      updateStatus(role, '正在保存信息…');
      await requestApi('/api/person', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role,
          certificateType: 0,
          personName: String(values.personName || '').trim(),
          personIDCard: String(values.personIDCard || '').trim(),
          personMobile: String(values.personMobile || '').trim(),
          identityImagesChanged:
            fileChanges[`${role}Identity`] === true,
        }),
      });
      removeDirty(role);
      setPreview(null);
      setFileChanges((current) => ({
        ...current,
        [`${role}Identity`]: false,
      }));
      setOcrCompleted((current) => ({ ...current, [role]: false }));
      await refresh(role);
      return true;
    } catch (error) {
      if (error instanceof Error) {
        updateStatus(role, error.message, 'error');
      }
      return false;
    } finally {
      setLoadingAction('');
    }
  };

  const checkPerson = async (role) => {
    if (dirtySteps.current.has(role) || !state.sections[role]) {
      const saved = await savePersonDraft(role);
      if (!saved) return false;
    }
    try {
      setLoadingAction(`${role}-check`);
      updateStatus(role, `正在校验${roles[role].shortTitle}信息…`);
      await requestApi('/api/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: role }),
      });
      removeDirty(role);
      setPreview(null);
      const nextState = await refresh(role);
      setStatus((current) => ({
        ...current,
        [role]: statusForCheck(role, nextState),
      }));
      return true;
    } catch (error) {
      if (error instanceof Error) {
        updateStatus(role, error.message, 'error');
      }
      return false;
    } finally {
      setLoadingAction('');
    }
  };

  const sendMobileCode = async (role) => {
    try {
      setLoadingAction(`${role}-code-send`);
      await requestApi('/api/mobile-code/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role }),
      });
      setVerificationCodes((current) => ({ ...current, [role]: '' }));
      setVerificationCooldowns((current) => ({ ...current, [role]: 60 }));
      setVerificationStatus((current) => ({
        ...current,
        [role]: {
          type: 'info',
          text: '验证码已发送，请查看手机短信。',
        },
      }));
      await refresh(role);
      return true;
    } catch (error) {
      setVerificationStatus((current) => ({
        ...current,
        [role]: { type: 'error', text: error.message },
      }));
      return false;
    } finally {
      setLoadingAction('');
    }
  };

  const verifyMobileCode = async (role, finishedCode) => {
    const code = String(
      finishedCode === undefined ? verificationCodes[role] || '' : finishedCode,
    ).trim();
    if (!/^[0-9]{4}$/.test(code)) {
      setVerificationStatus((current) => ({
        ...current,
        [role]: { type: 'error', text: '请输入 4 位验证码。' },
      }));
      return false;
    }
    try {
      setLoadingAction(`${role}-code-verify`);
      setVerificationStatus((current) => ({
        ...current,
        [role]: { type: 'info', text: '正在校验手机号验证码…' },
      }));
      await requestApi('/api/mobile-code/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, code }),
      });
      setVerificationCodes((current) => ({ ...current, [role]: '' }));
      removeDirty(role);
      setPreview(null);
      await refresh(role);
      setVerificationStatus((current) => ({
        ...current,
        [role]: { type: 'success', text: '手机号验证码校验通过。' },
      }));
      return true;
    } catch (error) {
      setVerificationCodes((current) => ({ ...current, [role]: '' }));
      setVerificationStatus((current) => ({
        ...current,
        [role]: { type: 'error', text: error.message },
      }));
      return false;
    } finally {
      setLoadingAction('');
    }
  };

  const continuePerson = (role) => {
    if (
      dirtySteps.current.has(role) ||
      !state.sections[role] ||
      !state.checks[role]?.matched
    ) {
      updateStatus(role, `请先完成${roles[role].shortTitle}信息校验。`, 'warning');
      return false;
    }
    if (!mobileVerificationDone(role, state)) {
      setVerificationStatus((current) => ({
        ...current,
        [role]: {
          type: 'error',
          text: '请先获取短信验证码并完成手机号校验。',
        },
      }));
      return false;
    }
    showStep(role === 'operator' ? 'responsible' : nextStep(state));
    return true;
  };

  const setResponsibleMode = async (sameOperator) => {
    try {
      setLoadingAction(`responsible-mode-${sameOperator}`);
      await requestApi('/api/responsible-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sameOperator }),
      });
      removeDirty('responsible');
      setPreview(null);
      await refresh(sameOperator ? '' : 'responsible');
      return true;
    } catch (error) {
      updateStatus('responsible', error.message, 'error');
      return false;
    } finally {
      setLoadingAction('');
    }
  };

  const saveAuthorization = async () => {
    try {
      setLoadingAction('authorization');
      if (state.powerOfAttorneyRequired) {
        const file = fileValue('power');
        if (file) {
          validateImageFile(file);
          updateStatus('authorization', '正在上传授权委托书…');
          await requestApi('/api/power-of-attorney', {
            method: 'POST',
            headers: { 'Content-Type': file.type },
            body: file,
          });
        } else if (!state.powerOfAttorneySaved) {
          throw new Error('请上传授权委托书。');
        }
      }
      const otherMaterials = (files.otherMaterials || [])
        .map(fileFromUploadItem)
        .filter(Boolean);
      if (fileChanges.otherMaterials === true) {
        for (let index = 0; index < otherMaterials.length; index += 1) {
          const file = otherMaterials[index];
          validateImageFile(file);
          await requestApi(
            `/api/other-material?index=${index}${index === 0 ? '&replace=1' : ''}`,
            {
              method: 'POST',
              headers: { 'Content-Type': file.type },
              body: file,
            },
          );
        }
      }
      updateStatus('authorization', '正在保存授权材料…');
      await requestApi('/api/authorization', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          otherMaterialsChanged: fileChanges.otherMaterials === true,
          otherMaterialCount: otherMaterials.length,
        }),
      });
      removeDirty('authorization');
      setPreview(null);
      setFileChanges((current) => ({
        ...current,
        otherMaterials: false,
      }));
      await refresh('');
      return true;
    } catch (error) {
      updateStatus('authorization', error.message, 'error');
      return false;
    } finally {
      setLoadingAction('');
    }
  };

  const loadPreview = useCallback(async () => {
    if (!state || !state.readyForPreview) return;
    try {
      setLoadingAction('preview');
      const payload = await requestApi('/api/preview', { method: 'POST' });
      setPreview(payload.preview);
      setConfirmed(false);
      updateStatus('review', '请核对以下信息后提交。', 'info');
    } catch (error) {
      updateStatus('review', error.message, 'error');
    } finally {
      setLoadingAction('');
    }
  }, [state, updateStatus]);

  useEffect(() => {
    if (activeStep === 'review' && state && state.readyForPreview && !preview) {
      loadPreview();
    }
  }, [activeStep, state, preview, loadPreview]);

  const submitQualification = async () => {
    if (!confirmed) {
      updateStatus('review', '请先勾选确认。', 'error');
      return;
    }
    if (state.checks.business.forceSkip) {
      const allowed = await new Promise((resolve) => {
        Modal.confirm({
          title: '确认强制提交',
          content: '企业信息核查失败，是否强制提交审核？',
          okText: '确认提交',
          cancelText: '返回检查',
          icon: <IconExclamationCircle />,
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        });
      });
      if (!allowed) return;
    }
    try {
      completionLocked.current = true;
      setLoadingAction('submit');
      updateStatus('review', '正在提交资质申请，请勿关闭页面…');
      const payload = await requestApi('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          confirmed: true,
          revision: preview.revision,
        }),
      });
      setHasChanges(false);
      setCompletion({
        status: 'submitted',
        qualificationId: payload.qualificationId,
      });
      finishLifecycle('submitted');
    } catch (error) {
      updateStatus('review', error.message, 'error');
      if (!error.outcomeUnknown) {
        completionLocked.current = false;
      } else {
        setCompletion({ status: 'outcome_unknown' });
        finishLifecycle('outcome_unknown');
      }
    } finally {
      setLoadingAction('');
    }
  };

  const abandonWizard = () => {
    Modal.confirm({
      title: '退出本次填写？',
      content: '退出后，本地未提交的资质草稿将被清除。',
      okText: '确认退出',
      cancelText: '继续填写',
      icon: <IconExclamationCircle />,
      onOk: async () => {
        try {
          setLoadingAction('abandon');
          await requestApi('/api/abandon', { method: 'POST' });
          completionLocked.current = true;
          setHasChanges(false);
          setCompletion({ status: 'abandoned' });
          finishLifecycle('abandoned');
        } catch (error) {
          Message.error(error.message);
          throw error;
        } finally {
          setLoadingAction('');
        }
      },
    });
  };

  const completeStep = async (step) => {
    if (step === 'base') return saveBase();
    if (step === 'business') return continueBusiness();
    if (step === 'legal') return saveLegal();
    if (step === 'operator') return continuePerson('operator');
    if (step === 'responsible') {
      if (state.sameOperator === true) {
        showStep(nextStep(state));
        return true;
      }
      if (state.sameOperator === null || state.sameOperator === undefined) {
        updateStatus(
          'responsible',
          '请先选择责任人是否与经办人相同。',
          'error',
        );
        return false;
      }
      return continuePerson('responsible');
    }
    if (step === 'authorization') return saveAuthorization();
    return true;
  };

  const navigateTo = async (target) => {
    if (!state || target === activeStep || !stepList.includes(target)) return;
    const targetIndex = stepList.indexOf(target);
    const currentIndex = stepList.indexOf(activeStep);
    if (
      targetIndex > currentIndex &&
      (dirtySteps.current.has(activeStep) || !stepDone(activeStep, state))
    ) {
      await completeStep(activeStep);
      return;
    }
    if (
      stepDone(target, state) ||
      target === nextStep(state) ||
      (target === 'review' && state.readyForPreview)
    ) {
      showStep(target);
    }
  };

  const goBack = () => {
    const index = stepList.indexOf(activeStep);
    if (index > 0) showStep(stepList[index - 1]);
  };

  const personForm = (role, withHeader = true) => {
    const imageRequired = personRequirement(role, 'image');
    const mobileRequired = personRequirement(role, 'mobile');
    const existing = (((state.savedData || {}).people || {})[role]) || {};
    const imageVisible = imageRequired || showPersonOcr[role];
    const values = personValues[role] || {};
    const roleDirty = dirtySteps.current.has(role);
    const roleCheck = state.checks[role] || {};
    const checkPassed = roleCheck.attempted && roleCheck.matched && !roleDirty;
    const checkFailed = roleCheck.attempted && !roleCheck.matched && !roleDirty;
    const hasSelectedIdentityImages = Boolean(
      fileValue(`${role}Front`) && fileValue(`${role}Back`),
    );
    const imagesReady = Boolean(
      !imageRequired ||
        existing.hasImages ||
        ocrCompleted[role] ||
        hasSelectedIdentityImages,
    );
    const fieldsReady = Boolean(
      String(values.personName || '').trim() &&
        /^[0-9]{17}[0-9Xx]$/.test(String(values.personIDCard || '').trim()) &&
        (!mobileRequired ||
          /^1[3-9][0-9]{9}$/.test(String(values.personMobile || '').trim())) &&
        imagesReady,
    );
    const statusValue = status[role] || statusForCheck(role, state);
    const mobileCodeRequired = Boolean(
      state.mobileVerificationRequired &&
        String(existing.personMobile || '').trim(),
    );
    const mobileCodeVerified = Boolean(
      (state.mobileVerifications || {})[role],
    );
    const mobileCodeCooldown = Number(verificationCooldowns[role] || 0);
    const mobileCodeBusy =
      loadingAction === `${role}-code-send` ||
      loadingAction === `${role}-code-verify`;
    const updatePersonValue = (field, value) => {
      setPersonValues((current) => ({
        ...current,
        [role]: { ...current[role], [field]: value },
      }));
      setStatus((current) => ({ ...current, [role]: null }));
      if (field === 'personMobile') {
        setVerificationCodes((current) => ({ ...current, [role]: '' }));
        setVerificationCooldowns((current) => ({ ...current, [role]: 0 }));
        setVerificationStatus((current) => ({ ...current, [role]: null }));
      }
      markChanged(role);
    };
    return (
      <>
        {withHeader && (
          <StepHeader
            title={roles[role].title}
            description="请按当前账号规则补充身份信息。OCR 识别结果可以继续修改。"
            status={stepDone(role, state) ? 'done' : 'active'}
          />
        )}
        {imageVisible && (
          <div className="form-grid person-upload-grid">
            <FilePicker
              fileKey={`${role}Front`}
              title="身份证人像面"
              required={imageRequired}
              files={files}
              setFiles={setFiles}
              markChanged={() => markChanged(role)}
              onFileSelected={(file) =>
                maybeRunPersonOcr(role, 'front', file)
              }
              onSelectionChange={() =>
                {
                  setOcrCompleted((current) => ({
                    ...current,
                    [role]: false,
                  }));
                  setFileChanges((current) => ({
                    ...current,
                    [`${role}Identity`]: true,
                  }));
                }
              }
              rectangular
            />
            <FilePicker
              fileKey={`${role}Back`}
              title="身份证国徽面"
              required={imageRequired}
              files={files}
              setFiles={setFiles}
              markChanged={() => markChanged(role)}
              onFileSelected={(file) =>
                maybeRunPersonOcr(role, 'back', file)
              }
              onSelectionChange={() =>
                {
                  setOcrCompleted((current) => ({
                    ...current,
                    [role]: false,
                  }));
                  setFileChanges((current) => ({
                    ...current,
                    [`${role}Identity`]: true,
                  }));
                }
              }
              rectangular
            />
          </div>
        )}
        {imageVisible && (
          <div className="entry-actions person-upload-status">
            {loadingAction === `${role}-ocr` && (
              <Spin dot tip="正在上传并识别…" />
            )}
            {ocrCompleted[role] && (
              <Tag color="green" icon={<IconCheck />}>
                识别完成
              </Tag>
            )}
            {existing.hasImages && !ocrCompleted[role] && (
              <Tag color="green" icon={<IconCheck />}>
                已保存身份证图片
              </Tag>
            )}
          </div>
        )}
        {!imageRequired && !showPersonOcr[role] && (
          <div className="entry-actions">
            <Button
              type="outline"
              icon={<IconUpload />}
              onClick={() => {
                setShowPersonOcr((current) => ({
                  ...current,
                  [role]: true,
                }));
                markChanged(role);
              }}
            >
              使用身份证图片自动识别
            </Button>
          </div>
        )}
        <Form
          layout="vertical"
        >
          <div className="form-grid">
            <Form.Item label="证件类型" required>
              <Radio.Group value={0}>
                <Radio value={0}>居民身份证</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item label={`${roles[role].shortTitle}姓名`} required>
              <Input
                allowClear
                value={values.personName}
                onChange={(value) => updatePersonValue('personName', value)}
                placeholder="如遇证件无法识别请手动输入"
              />
            </Form.Item>
            <Form.Item label="身份证号码" required>
              <Input
                allowClear
                maxLength={18}
                value={values.personIDCard}
                onChange={(value) => updatePersonValue('personIDCard', value)}
                placeholder="如遇证件无法识别请手动输入"
              />
            </Form.Item>
            <Form.Item
              label={`手机号${mobileRequired ? '' : '（选填）'}`}
              required={mobileRequired}
            >
              <Input
                allowClear
                maxLength={11}
                value={values.personMobile}
                onChange={(value) => updatePersonValue('personMobile', value)}
                placeholder={`请输入${roles[role].shortTitle}身份证实名的手机号码`}
              />
            </Form.Item>
          </div>
        </Form>
        <div className="entry-actions">
          <Button
            type="outline"
            icon={checkPassed ? <IconCheck /> : null}
            className={`person-check-button${
              checkPassed ? ' is-success' : ''
            }${checkFailed ? ' is-warning' : ''}`}
            disabled={
              checkPassed ||
              !fieldsReady ||
              loadingAction === `${role}-ocr`
            }
            loading={loadingAction === `${role}-check`}
            onClick={() => checkPerson(role)}
          >
            {checkPassed
              ? '校验已通过'
              : checkFailed
                ? '重新校验'
                : `${roles[role].shortTitle}信息校验`}
          </Button>
          <span
            className={`action-hint${
              checkPassed ? ' is-success' : ''
            }${checkFailed ? ' is-warning' : ''}`}
          >
            {checkPassed
              ? `${roles[role].shortTitle}信息校验通过`
              : checkFailed
                ? '校验未通过，请核对信息后重新校验'
                : fieldsReady
                  ? '信息填写完成后，请先进行校验'
                  : '请先完善身份信息'}
          </span>
        </div>
        {!checkPassed && <StepStatus status={statusValue} />}
        {checkPassed && mobileCodeRequired && (
          <div className="mobile-verification">
            <div className="mobile-verification-title">手机号校验</div>
            {mobileCodeVerified ? (
              <Tag color="green" icon={<IconCheck />}>
                手机号验证码校验通过
              </Tag>
            ) : (
              <>
                <div className="mobile-verification-controls">
                  <VerificationCode
                    value={verificationCodes[role] || ''}
                    length={4}
                    size="large"
                    disabled={mobileCodeBusy}
                    status={
                      verificationStatus[role]?.type === 'error'
                        ? 'error'
                        : undefined
                    }
                    validate={({ inputValue }) =>
                      /^[0-9]*$/.test(inputValue)
                    }
                    onChange={(value) =>
                      setVerificationCodes((current) => ({
                        ...current,
                        [role]: value,
                      }))
                    }
                    onFinish={(value) => verifyMobileCode(role, value)}
                  />
                  <Button
                    type="outline"
                    loading={loadingAction === `${role}-code-send`}
                    disabled={mobileCodeCooldown > 0 || mobileCodeBusy}
                    onClick={() => sendMobileCode(role)}
                  >
                    {mobileCodeCooldown > 0
                      ? `${mobileCodeCooldown}s 后重新获取`
                      : '获取验证码'}
                  </Button>
                </div>
                <StepStatus status={verificationStatus[role]} />
              </>
            )}
          </div>
        )}
        <div className="step-actions">
          <Button icon={<IconLeft />} onClick={goBack}>
            上一步
          </Button>
          <Button
            type="primary"
            icon={<IconRight />}
            iconOnly={false}
            onClick={() => continuePerson(role)}
          >
            确认并继续
          </Button>
        </div>
      </>
    );
  };

  if (status.boot && !state) {
    return (
      <main className="boot-error">
        <Alert type="error" showIcon title="无法加载资质表单" content={status.boot.text} />
      </main>
    );
  }

  if (!state) {
    return (
      <div className="completion">
        <Spin dot tip="正在读取资质申请规则…" />
      </div>
    );
  }

  if (completion) {
    if (completion.status === 'submitted') {
      return (
        <div className="completion">
          <Result
            status="success"
            title="资质申请已提交"
            subTitle={`资质申请 ID：${completion.qualificationId}。可以关闭页面。`}
          />
        </div>
      );
    }
    if (completion.status === 'abandoned') {
      return (
        <div className="completion">
          <Result
            status="info"
            title="已退出本次填写"
            subTitle="本地草稿已清除，没有提交资质申请。"
          />
        </div>
      );
    }
    return (
      <div className="completion">
        <Result
          status="warning"
          title="提交结果暂时无法确认"
          subTitle="请勿重复提交，Agent 将保留本次请求信息用于排查。"
        />
      </div>
    );
  }

  const expectedStep = nextStep(state);
  const currentStepIndex = stepList.indexOf(activeStep);
  const businessDirty = dirtySteps.current.has('business');
  const businessCheck = state.checks.business || {};
  const businessCheckPassed =
    businessCheck.attempted && businessCheck.matched && !businessDirty;
  const businessCheckFailed =
    businessCheck.attempted && !businessCheck.matched && !businessDirty;
  const businessFieldsReady = Boolean(
    pendingBusiness &&
      String(businessValues.businessCertificateName || '').trim() &&
      String(businessValues.unifiedSocialCreditIdentifier || '').trim() &&
      String(businessValues.legalPersonName || '').trim() &&
      Array.isArray(businessValues.businessCertificateValidityPeriod) &&
      businessValues.businessCertificateValidityPeriod.length === 2 &&
      (!businessImageRequired ||
        state.savedData.business.hasImage ||
        ocrCompleted.business),
  );
  const businessStatus =
    status.business || statusForCheck('business', state);
  const legalStatus =
    status.legal ||
    (state.legalCheckRequired
      ? statusForCheck('legal', state)
      : {
          type: 'info',
          text: state.legalAcknowledged
            ? '法人信息步骤已确认。'
            : '无需补充也可继续。',
        });

  const renderActiveStep = () => {
    if (activeStep === 'base') {
      return (
        <>
          <StepHeader
            title="基础信息"
            description="先确认资质归属和资质名称，后续步骤会复用这里的草稿值。"
            status={stepDone('base', state) ? 'done' : 'active'}
          />
          <Form
            form={baseForm}
            layout="vertical"
            initialValues={{
              purpose: Number(state.purpose || 1),
              materialName: state.materialName || '',
            }}
            scrollToFirstError
            onChange={(changed) => {
              markChanged('base');
              if (Object.prototype.hasOwnProperty.call(changed, 'purpose')) {
                setPurpose(Number(changed.purpose));
              }
              if (
                Object.prototype.hasOwnProperty.call(changed, 'materialName')
              ) {
                setMaterialNameTouched(true);
              }
            }}
          >
            <Form.Item
              field="purpose"
              label="资质归属"
              rules={[{ required: true, message: '请选择资质归属' }]}
            >
              <Radio.Group type="button">
                <Radio value={1}>
                  自用(营业证件为火山账号所对应的企业)
                </Radio>
                <Radio value={2}>
                  他用(营业证件非火山账号所对应的企业)
                </Radio>
              </Radio.Group>
            </Form.Item>
            <Alert
              className="purpose-help"
              type="info"
              showIcon
              content="“他用”是为其他主体发送短信，授权材料会在后续步骤中按账号规则处理。"
            />
            <Form.Item
              field="materialName"
              label="资质名称"
              extra="仅用于标识该资质信息，最多 20 个字。"
              rules={[
                { required: true, message: '请输入资质名称' },
                { maxLength: 20, message: '资质名称最多 20 个字' },
              ]}
            >
              <Input
                allowClear
                maxLength={20}
                showWordLimit
                placeholder="请输入易识别的资质名称"
              />
            </Form.Item>
          </Form>
          <StepStatus
            status={
              status.base || {
                type: state.baseSaved ? 'success' : 'info',
                text: state.baseSaved
                  ? '基础信息已保存。'
                  : '请确认资质归属并填写资质名称。',
              }
            }
          />
          <div className="step-actions">
            <Button
              type="primary"
              icon={<IconRight />}
              loading={loadingAction === 'base'}
              onClick={saveBase}
            >
              下一步
            </Button>
          </div>
        </>
      );
    }

    if (activeStep === 'business') {
      return (
        <>
          <StepHeader
            title="企业信息"
            description="上传营业证件进行 OCR，识别结果可以修改。"
            status={stepDone('business', state) ? 'done' : 'active'}
          />
          <Form
            layout="vertical"
          >
            <Form.Item
              label="营业证件类型"
              required
            >
              <Radio.Group
                type="button"
                value={businessCertificateType}
                onChange={(value) => {
                  setBusinessCertificateType(Number(value));
                  setOcrCompleted((current) => ({
                    ...current,
                    business: false,
                  }));
                  setStatus((current) => ({ ...current, business: null }));
                  markChanged('business');
                }}
              >
                <Radio value={1}>企业营业执照</Radio>
                <Radio value={4}>社会信用代码证书</Radio>
                <Radio value={7}>事业单位法人证书</Radio>
                <Radio value={6}>其他</Radio>
              </Radio.Group>
            </Form.Item>

            <div className="step-section">
              <FilePicker
                fileKey="business"
                title="营业证件附件"
                required={businessImageRequired}
                tip="支持jpg、png、jpeg格式的图片，每张图片不大于2MB；当营业证件照片为复印件、黑白照片时需要加盖红色企业公章，彩色图片无需加盖公章"
                rectangular
                files={files}
                setFiles={setFiles}
                markChanged={() => markChanged('business')}
                onSelectionChange={() =>
                  setOcrCompleted((current) => ({
                    ...current,
                    business: false,
                  }))
                }
                onFileSelected={runBusinessOcr}
                disabled={loadingAction === 'business-ocr'}
              />
              {loadingAction === 'business-ocr' && (
                <Tag color="blue">正在上传并识别</Tag>
              )}
              {state.savedData.business.hasImage && (
                <Tag color="green" icon={<IconCheck />}>
                  已保存营业证件附件
                </Tag>
              )}
            </div>

            <div className="step-section">
              <h3 className="step-section-title">证件信息</h3>
              <div className="form-grid">
                  <Form.Item
                    label="营业证件名称"
                    required
                  >
                    <Input
                      allowClear
                      value={businessValues.businessCertificateName}
                      onChange={(value) => {
                        setBusinessValues((current) => ({
                          ...current,
                          businessCertificateName: value,
                        }));
                        if (!materialNameTouched) {
                          baseForm.setFieldValue(
                            'materialName',
                            value.length <= 20 ? value : '',
                          );
                        }
                        setPendingBusiness(true);
                        setStatus((current) => ({ ...current, business: null }));
                        markChanged('business');
                      }}
                      placeholder="如遇营业执照无法识别请手动输入"
                    />
                  </Form.Item>
                  <Form.Item
                    label="统一社会信用代码"
                    required
                  >
                    <Input
                      allowClear
                      value={businessValues.unifiedSocialCreditIdentifier}
                      onChange={(value) => {
                        setBusinessValues((current) => ({
                          ...current,
                          unifiedSocialCreditIdentifier: value,
                        }));
                        setPendingBusiness(true);
                        setStatus((current) => ({ ...current, business: null }));
                        markChanged('business');
                      }}
                      placeholder="如遇营业执照无法识别请手动输入"
                    />
                  </Form.Item>
                  <Form.Item
                    className="span-2"
                    label="营业证件有效期"
                    extra="长期有效的营业证件，可以将办证时间作为开始时间，2099-12-31作为截止时间；如遇营业执照无法识别请手动输入"
                    required
                  >
                    <RangePicker
                      allowClear
                      format="YYYY-MM-DD"
                      value={businessValues.businessCertificateValidityPeriod}
                      onChange={(value) => {
                        setBusinessValues((current) => ({
                          ...current,
                          businessCertificateValidityPeriod: value || [],
                        }));
                        setPendingBusiness(true);
                        setStatus((current) => ({ ...current, business: null }));
                        markChanged('business');
                      }}
                      placeholder={['开始日期', '结束日期']}
                    />
                  </Form.Item>
                  <Form.Item
                    className="span-2"
                    label="法人姓名"
                    required
                  >
                    <Input
                      allowClear
                      value={businessValues.legalPersonName}
                      onChange={(value) => {
                        setBusinessValues((current) => ({
                          ...current,
                          legalPersonName: value,
                        }));
                        setLegalName(value);
                        setPendingBusiness(true);
                        setStatus((current) => ({ ...current, business: null }));
                        markChanged('business');
                      }}
                      placeholder="如遇营业执照无法识别请手动输入"
                    />
                  </Form.Item>
              </div>
            </div>
            <div className="entry-actions">
              <Button
                type="outline"
                icon={businessCheckPassed ? <IconCheck /> : null}
                className={`business-check-button${
                  businessCheckPassed ? ' is-success' : ''
                }${businessCheckFailed ? ' is-warning' : ''}`}
                disabled={
                  businessCheckPassed ||
                  !businessFieldsReady ||
                  loadingAction === 'business-ocr'
                }
                loading={loadingAction === 'business'}
                onClick={checkBusiness}
              >
                {businessCheckPassed
                  ? '校验已通过'
                  : businessCheckFailed
                    ? '重新校验'
                    : '营业证件有效性校验'}
              </Button>
              <span
                className={`action-hint${
                  businessCheckPassed ? ' is-success' : ''
                }${businessCheckFailed ? ' is-warning' : ''}`}
              >
                {businessCheckPassed
                  ? '营业证件信息校验通过'
                  : businessCheckFailed
                    ? '校验未通过，核对无误后仍可继续填写'
                    : businessFieldsReady
                      ? '信息填写完成后，请先进行校验'
                      : businessImageRequired
                        ? '请先上传营业证件并完善企业信息'
                        : '请先完善企业信息'}
              </span>
            </div>
          </Form>
          {!businessCheckPassed && <StepStatus status={businessStatus} />}
          <div className="step-actions">
            <Button icon={<IconLeft />} onClick={goBack}>
              上一步
            </Button>
            <Button
              type="primary"
              icon={<IconRight />}
              onClick={continueBusiness}
            >
              下一步
            </Button>
          </div>
        </>
      );
    }

    if (activeStep === 'legal') {
      const legalExisting =
        (((state.savedData || {}).people || {}).legal) || {};
      const isLegalIdCard =
        legalCertificateType === 0;
      const legalImagesVisible = isLegalIdCard;
      return (
        <>
          <StepHeader
            title="法人信息"
            description="法人姓名来自企业信息。身份证号、手机号和身份证图片均为选填。"
            status={stepDone('legal', state) ? 'done' : 'optional'}
          />
          <Form
            form={legalForm}
            layout="vertical"
            scrollToFirstError
            onChange={() => {
              markChanged('legal');
            }}
          >
            <Form.Item label="法人姓名">
              <div className="linked-value">
                {legalName || '请先填写企业信息中的法定代表人'}
              </div>
            </Form.Item>
            <div className="form-grid">
              <Form.Item label="法人证件类型">
                <Select
                  allowClear
                  value={legalCertificateType}
                  placeholder="请选择法人证件类型"
                  options={[
                    { label: '居民身份证', value: 0 },
                    { label: '护照', value: 1 },
                    { label: '港澳居民来往内地通行证', value: 2 },
                    { label: '台湾居民来往大陆通行证', value: 3 },
                    { label: '港澳台居民居住证', value: 4 },
                    { label: '其他类型证件', value: 9 },
                  ]}
                  onChange={(value) => {
                    const nextType =
                      value === undefined || value === null
                        ? undefined
                        : Number(value);
                    setLegalCertificateType(nextType);
                    setRecognizedLegalName('');
                    setOcrCompleted((current) => ({
                      ...current,
                      legal: false,
                    }));
                    setFiles((current) => {
                      [
                        ...(current.legalFront || []),
                        ...(current.legalBack || []),
                        ...(current.legalOther || []),
                      ].forEach(revokeLocalPreview);
                      return {
                        ...current,
                        legalFront: [],
                        legalBack: [],
                        legalOther: [],
                      };
                    });
                    setFileChanges((current) => ({
                      ...current,
                      legalIdentity: true,
                      legalDocuments: true,
                    }));
                    markChanged('legal');
                  }}
                />
              </Form.Item>
              <Form.Item
                field="personIDCard"
                label={
                  isLegalIdCard
                    ? '身份证号码（选填）'
                    : '证件号码（选填）'
                }
                rules={[
                  {
                    validator: (value, callback) => {
                      if (
                        !isLegalIdCard ||
                        !value ||
                        /^[0-9]{17}[0-9Xx]$/.test(value)
                      ) {
                        callback();
                      } else {
                        callback('请输入正确的 18 位身份证号');
                      }
                    },
                  },
                ]}
              >
                <Input
                  allowClear
                  maxLength={isLegalIdCard ? 18 : 64}
                  placeholder={
                    isLegalIdCard
                      ? '请输入身份证号'
                      : '请输入证件号码'
                  }
                />
              </Form.Item>
              <Form.Item
                field="personMobile"
                label="手机号（选填）"
                rules={[
                  {
                    validator: (value, callback) => {
                      if (!value || /^1[3-9][0-9]{9}$/.test(value)) callback();
                      else callback('请输入正确的 11 位手机号');
                    },
                  },
                ]}
              >
                <Input
                  allowClear
                  maxLength={11}
                  placeholder="例如 13800138000"
                />
              </Form.Item>
            </div>
          </Form>
          {legalImagesVisible && (
            <div className="form-grid person-upload-grid">
              <FilePicker
                fileKey="legalFront"
                title="身份证人像面"
                files={files}
                setFiles={setFiles}
                markChanged={() => markChanged('legal')}
                onFileSelected={(file) =>
                  maybeRunPersonOcr('legal', 'front', file)
                }
                onSelectionChange={() => {
                  setOcrCompleted((current) => ({
                    ...current,
                    legal: false,
                  }));
                  setFileChanges((current) => ({
                    ...current,
                    legalIdentity: true,
                  }));
                }}
                rectangular
              />
              <FilePicker
                fileKey="legalBack"
                title="身份证国徽面"
                files={files}
                setFiles={setFiles}
                markChanged={() => markChanged('legal')}
                onFileSelected={(file) =>
                  maybeRunPersonOcr('legal', 'back', file)
                }
                onSelectionChange={() => {
                  setOcrCompleted((current) => ({
                    ...current,
                    legal: false,
                  }));
                  setFileChanges((current) => ({
                    ...current,
                    legalIdentity: true,
                  }));
                }}
                rectangular
              />
            </div>
          )}
          {legalCertificateType !== undefined && legalCertificateType !== 0 && (
            <FilePicker
              fileKey="legalOther"
              title="非身份证证件附件（选填）"
              tip="支持 JPG、JPEG、PNG，单张不大于 2 MB；最多支持上传两张"
              files={files}
              setFiles={setFiles}
              markChanged={() => {
                markChanged('legal');
              }}
              onSelectionChange={() =>
                setFileChanges((current) => ({
                  ...current,
                  legalDocuments: true,
                }))
              }
              maxCount={2}
              rectangular
              uploadTitle="点击或拖拽图片到这里"
            />
          )}
          <div className="entry-actions">
            {loadingAction === 'legal-ocr' && (
              <Spin dot tip="正在上传并识别…" />
            )}
            {ocrCompleted.legal && (
              <Tag color="green" icon={<IconCheck />}>
                识别完成
              </Tag>
            )}
            {isLegalIdCard &&
              legalExisting.hasIdentityImages && (
              <Tag color="green" icon={<IconCheck />}>
                已保存身份证图片
              </Tag>
            )}
            {legalCertificateType !== undefined &&
              legalCertificateType !== 0 &&
              legalExisting.hasDocuments && (
              <Tag color="green" icon={<IconCheck />}>
                已保存非身份证证件附件
              </Tag>
            )}
          </div>
          <StepStatus status={legalStatus} />
          <div className="step-actions">
            <Button icon={<IconLeft />} onClick={goBack}>
              上一步
            </Button>
            <Button
              type="primary"
              icon={<IconRight />}
              loading={loadingAction === 'legal'}
              onClick={saveLegal}
            >
              确认并继续
            </Button>
          </div>
        </>
      );
    }

    if (activeStep === 'operator') return personForm('operator');

    if (activeStep === 'responsible') {
      const same = state.sameOperator;
      return (
        <>
          <StepHeader
            title="责任人信息"
            description="责任人与经办人相同时直接复用已保存的信息和校验结果。"
            status={stepDone('responsible', state) ? 'done' : 'active'}
          />
          <div className="responsible-choice">
            <p className="responsible-choice-title">
              责任人和经办人是同一个人吗？
            </p>
            <p className="responsible-choice-copy">
              选择“是”后无需重复填写和校验。
            </p>
            <div className="responsible-actions">
              <Button
                type={same === true ? 'primary' : 'secondary'}
                loading={loadingAction === 'responsible-mode-true'}
                onClick={() => setResponsibleMode(true)}
              >
                是同一个人
              </Button>
              <Button
                type={same === false ? 'primary' : 'secondary'}
                loading={loadingAction === 'responsible-mode-false'}
                onClick={() => setResponsibleMode(false)}
              >
                不是同一个人
              </Button>
            </div>
          </div>
          {same === true && (
            <>
              <Alert
                className="step-status"
                type="success"
                showIcon
                content="责任人将复用经办人信息和校验结果。"
              />
              <div className="step-actions">
                <Button icon={<IconLeft />} onClick={goBack}>
                  上一步
                </Button>
                <Button
                  type="primary"
                  icon={<IconRight />}
                  onClick={() => showStep(nextStep(state))}
                >
                  继续
                </Button>
              </div>
            </>
          )}
          {same === false && (
            <div className="step-section">
              {personForm('responsible', false)}
            </div>
          )}
          {same === null && <StepStatus status={status.responsible} />}
        </>
      );
    }

    if (activeStep === 'authorization') {
      const required = state.powerOfAttorneyRequired;
      return (
        <>
          <StepHeader
            title="授权材料"
            description={
              required
                ? '授权方来自营业证件，被授权方来自当前火山账号；请提供授权委托书。'
                : '授权方来自营业证件，被授权方来自当前火山账号；无需额外上传授权委托书。'
            }
            status={stepDone('authorization', state) ? 'done' : 'active'}
          />
          <div className="form-grid">
            <Form.Item label="授权方" required>
              <Input
                value={state.authorizer || ''}
                disabled
                placeholder="来自营业证件名称"
              />
            </Form.Item>
            <Form.Item label="被授权方" required>
              <Input
                value={state.authorizee || ''}
                disabled
                placeholder="来自当前火山账号企业信息"
              />
            </Form.Item>
          </div>
          {required && (
            <FilePicker
              fileKey="power"
              title="授权委托书图片"
              required
              files={files}
              setFiles={setFiles}
              markChanged={() => markChanged('authorization')}
            />
          )}
          {state.powerOfAttorneySaved && (
            <Tag color="green" icon={<IconCheck />}>
              已保存授权委托书
            </Tag>
          )}
          <div className="step-section">
            <FilePicker
              fileKey="otherMaterials"
              title="其他材料（选填）"
              tip="支持 JPG、JPEG、PNG，单张不大于 2 MB；最多支持上传五张"
              files={files}
              setFiles={setFiles}
              markChanged={() => markChanged('authorization')}
              onSelectionChange={() =>
                setFileChanges((current) => ({
                  ...current,
                  otherMaterials: true,
                }))
              }
              maxCount={5}
            />
            {state.otherMaterialCount > 0 &&
              fileChanges.otherMaterials !== true && (
                <Tag color="green" icon={<IconCheck />}>
                  已保存 {state.otherMaterialCount} 份其他材料
                </Tag>
              )}
          </div>
          <StepStatus
            status={
              status.authorization || {
                type: stepDone('authorization', state) ? 'success' : 'info',
                text: stepDone('authorization', state)
                  ? '授权材料步骤已完成。'
                  : required
                    ? '请上传授权委托书。'
                    : '确认后即可继续。',
              }
            }
          />
          <div className="step-actions">
            <Button icon={<IconLeft />} onClick={goBack}>
              上一步
            </Button>
            <Button
              type="primary"
              icon={<IconRight />}
              loading={loadingAction === 'authorization'}
              onClick={saveAuthorization}
            >
              {required ? '上传并继续' : '确认并继续'}
            </Button>
          </div>
        </>
      );
    }

    const previewPeople = preview ? Object.values(preview.people || {}) : [];
    return (
      <>
        <StepHeader
          title="核对并提交"
          description="请核对完整信息。返回修改后，页面会重新生成预览。"
          status="active"
        />
        {loadingAction === 'preview' && (
          <Spin dot tip="正在生成预览…" />
        )}
        {preview && (
          <>
            <div className="review-section">
              <h3>资质信息</h3>
              <Descriptions
                border
                column={compact ? 1 : 2}
                data={[
                  { label: '资质名称', value: preview.materialName },
                  { label: '用途', value: preview.purpose },
                  {
                    label: '授权委托书',
                    value: preview.powerOfAttorney,
                  },
                  ...(preview.authorization
                    ? [
                        {
                          label: '授权方',
                          value: preview.authorization.authorizer,
                        },
                        {
                          label: '被授权方',
                          value: preview.authorization.authorizee,
                        },
                        {
                          label: '其他材料',
                          value: `${preview.authorization.otherMaterialCount} 份`,
                        },
                      ]
                    : []),
                  {
                    label: '企业校验',
                    value: preview.checks.business,
                  },
                  {
                    label: '营业证件名称',
                    value: preview.business.businessCertificateName,
                  },
                  {
                    label: '统一社会信用代码',
                    value:
                      preview.business.unifiedSocialCreditIdentifier,
                  },
                  {
                    label: '法人姓名',
                    value: preview.business.legalPersonName,
                  },
                  {
                    label: '营业证件有效期',
                    value: `${preview.business.businessCertificateValidityPeriodStart} 至 ${preview.business.businessCertificateValidityPeriodEnd}`,
                  },
                ]}
              />
            </div>
            {previewPeople.map((person) => (
              <div className="review-section" key={person.label}>
                <h3>{person.label}信息</h3>
                <Descriptions
                  border
                  column={compact ? 1 : 3}
                  data={[
                    { label: '姓名', value: person.personName },
                    { label: '身份证号', value: person.personIDCard },
                    {
                      label: '手机号',
                      value: person.personMobile || '未填写',
                    },
                  ]}
                />
              </div>
            ))}
            <div className="review-confirm">
              <Checkbox
                checked={confirmed}
                onChange={(value) => {
                  setConfirmed(value);
                  markChanged('review');
                }}
              >
                我已核对以上内容，同意提交审核
              </Checkbox>
            </div>
          </>
        )}
        <StepStatus status={status.review} />
        <div className="step-actions">
          <Button icon={<IconLeft />} onClick={goBack}>
            上一步
          </Button>
          <Button
            type="primary"
            icon={<IconCheck />}
            disabled={!preview}
            loading={loadingAction === 'submit'}
            onClick={submitQualification}
          >
            提交资质
          </Button>
        </div>
      </>
    );
  };

  const stepItems = stepList.map((step) => {
    const done = stepDone(step, state);
    const enabled =
      done ||
      step === expectedStep ||
      step === activeStep ||
      (step === 'review' && state.readyForPreview);
    return {
      key: step,
      title: stepTitles[step],
      className: enabled ? 'wizard-step-enabled' : '',
      disabled: !enabled,
    };
  });

  return (
    <div className="wizard-page">
      <header className="wizard-header">
        <div className="wizard-header-inner">
          <div className="wizard-title-row">
            <div>
              <div className="wizard-brand">火山引擎短信</div>
              <h1 className="wizard-title">创建短信资质</h1>
              <p className="wizard-subtitle">
                按步骤填写企业与人员信息，系统会在进入下一步前完成必要校验。
              </p>
            </div>
            <Button
              status="danger"
              icon={<IconClose />}
              loading={loadingAction === 'abandon'}
              disabled={completionLocked.current}
              onClick={abandonWizard}
            >
              退出填写
            </Button>
          </div>
          <Alert
            className="wizard-privacy"
            type="success"
            showIcon
            content="姓名、身份证号和手机号仅以掩码提供给 Agent 排查；图片直接上传材料服务，不进入聊天或模型上下文。完成前请保持本页面打开。"
          />
        </div>
      </header>

      <main className="wizard-body">
        <section className="wizard-workspace">
          <aside className="wizard-sidebar">
            <div className="wizard-sidebar-title">申请进度</div>
            <Steps
              current={currentStepIndex + 1}
              direction={compact ? 'horizontal' : 'vertical'}
              size="small"
              onChange={(index) => {
                const item = stepItems[index - 1];
                if (item && !item.disabled) navigateTo(item.key);
              }}
            >
              {stepItems.map((item) => (
                <Steps.Step
                  key={item.key}
                  title={item.title}
                  disabled={item.disabled}
                  className={item.className}
                />
              ))}
            </Steps>
          </aside>
          <section className="wizard-content">{renderActiveStep()}</section>
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
      <main className="boot-error">
        <Alert
          type="error"
          showIcon
          title="资质表单加载失败"
          content="请关闭当前页面，并从资质创建入口重新打开。"
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
