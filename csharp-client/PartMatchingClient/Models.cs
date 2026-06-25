using System.Text.Json.Serialization;

namespace PartMatching;

/// <summary>照合 API のレスポンス（/api/v1/inspect）。</summary>
public sealed record InspectResponse
{
    [JsonPropertyName("result")] public string Result { get; init; } = "";
    [JsonPropertyName("action")] public string Action { get; init; } = "";
    [JsonPropertyName("predicted_part_no")] public string? PredictedPartNo { get; init; }
    [JsonPropertyName("expected_part_no")] public string? ExpectedPartNo { get; init; }
    [JsonPropertyName("confidence")] public double Confidence { get; init; }
    [JsonPropertyName("margin")] public double Margin { get; init; }
    [JsonPropertyName("top_candidates")] public List<Candidate> TopCandidates { get; init; } = new();
    [JsonPropertyName("quality")] public QualityInfo? Quality { get; init; }
    [JsonPropertyName("reason")] public string Reason { get; init; } = "";
    [JsonPropertyName("processing_time_ms")] public double ProcessingTimeMs { get; init; }
    [JsonPropertyName("log_id")] public long? LogId { get; init; }
}

public sealed record Candidate
{
    [JsonPropertyName("part_no")] public string PartNo { get; init; } = "";
    [JsonPropertyName("score")] public double Score { get; init; }
    [JsonPropertyName("confidence")] public double Confidence { get; init; }
    [JsonPropertyName("group_id")] public int? GroupId { get; init; }
}

public sealed record QualityInfo
{
    [JsonPropertyName("ok")] public bool Ok { get; init; }
    [JsonPropertyName("action")] public string Action { get; init; } = "";
    [JsonPropertyName("issues")] public List<string> Issues { get; init; } = new();
}

/// <summary>現場設備が取るべきアクション。</summary>
public enum LineAction { Pass, Block, ManualCheck, Retake }
