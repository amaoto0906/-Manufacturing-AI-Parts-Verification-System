using System.Net.Http.Headers;
using System.Text.Json;

namespace PartMatching;

/// <summary>
/// 部品照合 AI への REST クライアント。既存 C# システム（出荷管理・PLC連携等）から
/// 本クラス経由で照合を依頼し、戻り値の result/action に従ってライン制御を行う。
/// 低遅延が必要な場合は gRPC 版に差し替え可能（API 仕様は docs/04_api_spec.md）。
/// </summary>
public sealed class PartMatchingApiClient : IDisposable
{
    private readonly HttpClient _http;

    public PartMatchingApiClient(string baseUrl, TimeSpan? timeout = null)
    {
        _http = new HttpClient { BaseAddress = new Uri(baseUrl), Timeout = timeout ?? TimeSpan.FromSeconds(10) };
    }

    /// <summary>画像ファイルを照合する。</summary>
    public async Task<InspectResponse> InspectAsync(
        string imagePath, string? expectedPartNo,
        string? operatorId = null, string? lineId = null, bool runQuality = true)
    {
        await using var fs = File.OpenRead(imagePath);
        return await InspectAsync(fs, Path.GetFileName(imagePath), expectedPartNo, operatorId, lineId, runQuality);
    }

    /// <summary>画像ストリームを照合する（カメラSDKから直接渡す用途）。</summary>
    public async Task<InspectResponse> InspectAsync(
        Stream image, string fileName, string? expectedPartNo,
        string? operatorId = null, string? lineId = null, bool runQuality = true)
    {
        using var form = new MultipartFormDataContent();
        var fileContent = new StreamContent(image);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue("image/png");
        form.Add(fileContent, "file", fileName);
        if (expectedPartNo is not null) form.Add(new StringContent(expectedPartNo), "expected_part_no");
        if (operatorId is not null) form.Add(new StringContent(operatorId), "operator_id");
        if (lineId is not null) form.Add(new StringContent(lineId), "line_id");
        form.Add(new StringContent(runQuality ? "true" : "false"), "run_quality");

        using var resp = await _http.PostAsync("/api/v1/inspect", form);
        var body = await resp.Content.ReadAsStringAsync();
        if (!resp.IsSuccessStatusCode)
            throw new HttpRequestException($"照合APIエラー {(int)resp.StatusCode}: {body}");

        return JsonSerializer.Deserialize<InspectResponse>(body)
               ?? throw new InvalidOperationException("レスポンスを解析できません。");
    }

    /// <summary>action 文字列を列挙へ変換。</summary>
    public static LineAction ToLineAction(string action) => action switch
    {
        "pass" => LineAction.Pass,
        "block" => LineAction.Block,
        "retake" => LineAction.Retake,
        _ => LineAction.ManualCheck,
    };

    public void Dispose() => _http.Dispose();
}
