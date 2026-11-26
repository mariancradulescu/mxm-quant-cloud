using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Mxm.Core;

// Historical books contain serialized sub-ledgers. A long replay can exceed
// the JSON writer's single-token limit while all of the underlying data is valid.
internal static class NativeHistoricalCheckpointJson
{
    internal const int ChunkCharacters = 8 * 1024 * 1024;
    internal static readonly JsonSerializerOptions Options = new() { Converters = { new CheckpointStringConverter() } };

    sealed class CheckpointStringConverter : JsonConverter<string>
    {
        public override string Read(ref Utf8JsonReader reader,Type type,JsonSerializerOptions options)
        {
            if(reader.TokenType==JsonTokenType.String)return reader.GetString()!;
            if(reader.TokenType!=JsonTokenType.StartArray)throw new JsonException("Invalid checkpoint text");
            var value=new StringBuilder();
            while(reader.Read()&&reader.TokenType==JsonTokenType.String)
                value.Append(reader.GetString());
            if(reader.TokenType!=JsonTokenType.EndArray||value.Length==0)
                throw new JsonException("Invalid checkpoint text fragments");
            return value.ToString();
        }

        public override void Write(Utf8JsonWriter writer,string value,JsonSerializerOptions options)
        {
            if(value.Length<=ChunkCharacters)
            {
                writer.WriteStringValue(value);
                return;
            }
            writer.WriteStartArray();
            for(int start=0;start<value.Length;)
            {
                int length=Math.Min(ChunkCharacters,value.Length-start);
                if(start+length<value.Length&&char.IsHighSurrogate(value[start+length-1]))length--;
                writer.WriteStringValue(value.AsSpan(start,length));
                start+=length;
            }
            writer.WriteEndArray();
        }

        public override string ReadAsPropertyName(ref Utf8JsonReader reader,Type type,JsonSerializerOptions options)
            =>reader.GetString()!;

        public override void WriteAsPropertyName(Utf8JsonWriter writer,string value,JsonSerializerOptions options)
            =>writer.WritePropertyName(value);
    }
}
