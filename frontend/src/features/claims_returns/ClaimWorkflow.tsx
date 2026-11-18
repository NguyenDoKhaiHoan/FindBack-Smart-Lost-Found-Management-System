import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiFeedback } from '../../components/ui/live'
import { formatDate, imageTypes, maxImageSize } from '../../components/ui/live-format'
import { ApiError, type ClaimDetail } from '../../lib/api'
import { returnApi } from '../../lib/api/system'
import { useSession } from '../auth/session'

export function ClaimEvidenceForm({ claim }: { claim: ClaimDetail }) {
  const client = useQueryClient()
  const [message, setMessage] = useState('')
  const [fileError, setFileError] = useState('')
  const add = useMutation({
    mutationFn: async ({ text, file }: { text: string; file: File | null }) => {
      let attachment = {}
      if (file) {
        const data = await readDataUrl(file)
        attachment = {
          image_base64: data.slice(data.indexOf(',') + 1),
          image_content_type: file.type,
        }
      }
      return returnApi.evidence(claim.id, {
        evidence_description: text,
        expected_version: claim.version,
        ...attachment,
      })
    },
    onSuccess: async () => {
      setMessage('Đã bổ sung bằng chứng.')
      await client.invalidateQueries({ queryKey: ['claims'] })
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409)
        void client.invalidateQueries({ queryKey: ['claims'] })
    },
  })
  return (
    <details>
      <summary>Bổ sung bằng chứng</summary>
      <form
        key={add.isSuccess ? claim.version : 'draft'}
        className="live-stack"
        onSubmit={(event) => {
          event.preventDefault()
          const form = new FormData(event.currentTarget)
          const text = String(form.get('evidence')).trim()
          const item = form.get('image')
          const file = item instanceof File && item.size > 0 ? item : null
          setMessage('')
          if (file && (!imageTypes.includes(file.type) || file.size > maxImageSize)) {
            setFileError('Ảnh bằng chứng phải là JPEG, PNG hoặc WebP, tối đa 5 MiB.')
            return
          }
          if (text.length < 10) {
            setFileError('Mô tả bằng chứng cần ít nhất 10 ký tự.')
            return
          }
          setFileError('')
          add.mutate({ text, file })
        }}
      >
        <label className="field">
          Mô tả bổ sung
          <textarea name="evidence" required minLength={10} maxLength={5000} rows={3} />
        </label>
        <label className="field">
          Ảnh bằng chứng riêng tư
          <input name="image" type="file" accept={imageTypes.join(',')} />
        </label>
        {fileError && (
          <p className="error-state" role="alert">
            {fileError}
          </p>
        )}
        <ApiFeedback error={add.error} />
        {message && <p role="status">{message}</p>}
        <button className="button button-secondary" disabled={add.isPending} type="submit">
          Gửi bằng chứng bổ sung
        </button>
      </form>
    </details>
  )
}

function readDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Không thể đọc ảnh'))
    reader.onload = () => resolve(String(reader.result))
    reader.readAsDataURL(file)
  })
}

export function EvidenceFile({ claimId, evidenceId }: { claimId: string; evidenceId: string }) {
  const download = useMutation({
    mutationFn: async () => {
      const image = await returnApi.file(claimId, evidenceId)
      const url = URL.createObjectURL(image)
      const link = document.createElement('a')
      link.href = url
      const extension = image.type === 'image/jpeg' ? 'jpg' : image.type.split('/')[1] || 'img'
      link.download = `bang-chung.${extension}`
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    },
  })
  return (
    <div className="live-actions">
      <button
        className="text-link"
        type="button"
        disabled={download.isPending}
        onClick={() => download.mutate()}
      >
        Tải ảnh bằng chứng nếu có
      </button>
      <ApiFeedback error={download.error} />
    </div>
  )
}

export function ReturnActions({
  claim,
  isClaimant,
  busy,
}: {
  claim: ClaimDetail
  isClaimant: boolean
  busy: boolean
}) {
  const { actorId } = useSession()
  const client = useQueryClient()
  const [confirmed, setConfirmed] = useState(false)
  const id = claim.return_summary?.id
  const details = useQuery({
    queryKey: ['returns', actorId, id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => returnApi.detail(id!, signal),
  })
  const save = useMutation({
    mutationFn: ({ date, note }: { date?: string; note?: string }) =>
      id
        ? returnApi.handover(id, claim.version)
        : returnApi.arrange({
            claim_id: claim.id,
            expected_version: claim.version,
            scheduled_at: date ? new Date(date).toISOString() : null,
            meeting_note: note || null,
          }),
    onSuccess: async (result) => {
      client.setQueryData(['returns', actorId, result.id], result)
      await Promise.all(
        ['claims', 'returns', 'notifications'].map((key) =>
          client.invalidateQueries({ queryKey: [key] }),
        ),
      )
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409)
        void client.invalidateQueries({ queryKey: ['claims'] })
    },
  })
  return (
    <div className="live-stack">
      {id && (
        <ApiFeedback
          pending={details.isPending}
          error={details.error}
          retry={() => void details.refetch()}
        />
      )}
      {details.data?.scheduled_at && <p>Thời gian hẹn: {formatDate(details.data.scheduled_at)}</p>}
      {details.data?.meeting_note && (
        <p className="preserve-lines">Ghi chú trao trả: {details.data.meeting_note}</p>
      )}
      {claim.status === 'APPROVED' &&
        isClaimant &&
        claim.return_summary?.status !== 'HANDED_OVER' && (
          <p>{id ? 'Chờ chủ tin ghi nhận bàn giao.' : 'Chờ chủ tin lập phiên trao trả.'}</p>
        )}
      {!isClaimant && claim.status === 'APPROVED' && !id && (
        <form
          className="live-stack"
          onSubmit={(event) => {
            event.preventDefault()
            const data = new FormData(event.currentTarget)
            save.mutate({ date: String(data.get('date')), note: String(data.get('note')).trim() })
          }}
        >
          <label className="field">
            Thời gian hẹn
            <input type="datetime-local" name="date" />
          </label>
          <label className="field">
            Ghi chú trao trả
            <textarea name="note" rows={3} maxLength={1000} />
          </label>
          <button className="button button-primary" type="submit" disabled={busy || save.isPending}>
            Lập phiên trao trả
          </button>
        </form>
      )}
      {!isClaimant &&
        claim.status === 'APPROVED' &&
        claim.return_summary?.status === 'ARRANGED' && (
          <div className="live-stack">
            <label className="claim-checkbox">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />{' '}
              Tôi đã trực tiếp giao đồ cho người nhận.
            </label>
            <button
              className="button button-primary"
              type="button"
              disabled={!confirmed || busy || save.isPending}
              onClick={() => save.mutate({})}
            >
              Ghi nhận đã bàn giao
            </button>
          </div>
        )}
      {!isClaimant &&
        claim.status === 'APPROVED' &&
        claim.return_summary?.status === 'HANDED_OVER' && (
          <p>Đã ghi nhận bàn giao. Chờ người nhận xác nhận.</p>
        )}
      <ApiFeedback error={save.error} />
    </div>
  )
}
