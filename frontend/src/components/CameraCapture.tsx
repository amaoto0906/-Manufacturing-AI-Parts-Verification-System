import { useCallback, useEffect, useRef, useState } from "react";

interface Props {
  onCapture: (blob: Blob) => void;
  onClose: () => void;
}

type Facing = "environment" | "user";

/**
 * PC/モバイルのカメラで直接撮影するコンポーネント。
 * getUserMedia はセキュアコンテキスト(HTTPS または localhost)でのみ利用可能。
 * モバイルから LAN 越しに使う場合は HTTPS 起動が必要（README 参照）。
 */
export function CameraCapture({ onCapture, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [facing, setFacing] = useState<Facing>("environment");

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const start = useCallback(
    async (mode: Facing) => {
      setError("");
      setReady(false);
      if (!window.isSecureContext) {
        setError(
          "カメラはHTTPSまたはlocalhostでのみ利用できます。モバイルから使う場合は HTTPS で起動してください（make api-https）。",
        );
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("このブラウザはカメラ(getUserMedia)に対応していません。");
        return;
      }
      try {
        stop();
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: mode, width: { ideal: 1280 }, height: { ideal: 1280 } },
          audio: false,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }
        setReady(true);
      } catch (e) {
        setError("カメラにアクセスできません: " + (e as Error).message + "（権限の許可を確認してください）");
      }
    },
    [stop],
  );

  useEffect(() => {
    start(facing);
    return () => stop();
    // 初回のみ起動。切替は switchCamera で行う。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchCamera = () => {
    const next: Facing = facing === "environment" ? "user" : "environment";
    setFacing(next);
    start(next);
  };

  const capture = () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const w = v.videoWidth;
    const h = v.videoHeight;
    const s = Math.min(w, h); // 中央正方形クロップ（部品が中央にある前提）
    const canvas = document.createElement("canvas");
    canvas.width = s;
    canvas.height = s;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(v, (w - s) / 2, (h - s) / 2, s, s, 0, 0, s, s);
    canvas.toBlob((blob) => {
      if (blob) {
        stop();
        onCapture(blob);
      }
    }, "image/png");
  };

  const close = () => {
    stop();
    onClose();
  };

  return (
    <div className="camera-panel">
      <div className="camera-stage">
        <video ref={videoRef} className="camera-video" playsInline muted autoPlay />
        <div className="camera-reticle" aria-hidden="true" />
        {!ready && !error && <div className="camera-status">カメラ起動中…</div>}
        {error && <div className="camera-status camera-error">{error}</div>}
      </div>
      <div className="btn-row">
        <button className="btn btn-primary" onClick={capture} disabled={!ready}>
          ● 撮影してセット
        </button>
        <button className="btn" onClick={switchCamera} disabled={!ready}>
          ⇄ カメラ切替
        </button>
        <button className="btn" onClick={() => start(facing)}>
          ↻ 再試行
        </button>
        <button className="btn" onClick={close}>
          閉じる
        </button>
      </div>
      <p className="muted" style={{ margin: "6px 0 0", fontSize: 12 }}>
        モバイル背面カメラは「カメラ切替」で選択。HTTPSでない場合はカメラが起動しません。
      </p>
    </div>
  );
}
